"""
collector_daemon.py — Standalone background data collector for GalacticCIC.

Runs independently of the dashboard, collecting metrics on a tiered schedule
and writing to the SQLite database. The dashboard reads from the same DB.

Usage:
    galactic-cic-collector              # Run in foreground (for systemd)
    galactic-cic-collector --interval 30  # Custom fast-tier interval
"""

import asyncio
import signal
import sys
import time
import logging
from datetime import datetime, timezone

from galactic_cic.data.collectors import (
    get_agents_data,
    get_openclaw_status,
    get_server_health,
    get_cron_jobs,
    get_security_status,
    get_activity_log,
    get_network_activity,
    get_top_ips,
    get_top_processes,
    get_ssh_login_summary,
    get_openclaw_logs,
    get_error_summary,
    get_channels_status,
    get_update_status,
    resolve_ip,
    scan_attacker_ip,
    get_ip_geolocation,
)
from galactic_cic.db.database import MetricsDB
from galactic_cic.db.recorder import MetricsRecorder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [collector] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Tiered intervals (seconds)
TIER_FAST = 30       # server health, top processes
TIER_MEDIUM = 120    # cron, activity, logs, network
TIER_SLOW = 300      # agents, openclaw status, security, channels, update
TIER_GLACIAL = 900   # attacker scans, geolocation, DNS resolution


class CollectorDaemon:
    """Background data collector with tiered refresh."""

    def __init__(self, fast_interval=TIER_FAST):
        self.fast_interval = fast_interval
        self.running = True
        self.db = MetricsDB()
        self.recorder = MetricsRecorder(self.db)
        self._timestamps = {}  # source -> monotonic time
        self._cached_data = {}  # source -> last result

    def _is_due(self, source, ttl):
        now = time.monotonic()
        return (now - self._timestamps.get(source, 0)) >= ttl

    def _mark(self, source):
        self._timestamps[source] = time.monotonic()

    async def collect_once(self):
        """Run one collection cycle with tiered scheduling."""
        tasks = {}

        # FAST tier
        if self._is_due("server_health", TIER_FAST):
            tasks["server_health"] = get_server_health()
        if self._is_due("top_processes", TIER_FAST):
            tasks["top_processes"] = get_top_processes()

        # MEDIUM tier
        if self._is_due("cron_jobs", TIER_MEDIUM):
            tasks["cron_jobs"] = get_cron_jobs()
        if self._is_due("activity_log", TIER_MEDIUM):
            tasks["activity_log"] = get_activity_log()
        if self._is_due("openclaw_logs", TIER_MEDIUM):
            tasks["openclaw_logs"] = get_openclaw_logs(limit=20)
        if self._is_due("error_summary", TIER_MEDIUM):
            tasks["error_summary"] = get_error_summary()
        if self._is_due("network_activity", TIER_MEDIUM):
            tasks["network_activity"] = get_network_activity()

        # SLOW tier
        if self._is_due("agents_data", TIER_SLOW):
            tasks["agents_data"] = get_agents_data()
        if self._is_due("openclaw_status", TIER_SLOW):
            tasks["openclaw_status"] = get_openclaw_status()
        if self._is_due("security_status", TIER_SLOW):
            tasks["security_status"] = get_security_status()
        if self._is_due("ssh_login_summary", TIER_SLOW):
            tasks["ssh_login_summary"] = get_ssh_login_summary()
        if self._is_due("channels_status", TIER_SLOW):
            tasks["channels_status"] = get_channels_status()
        if self._is_due("update_status", TIER_SLOW):
            tasks["update_status"] = get_update_status()

        if not tasks:
            return

        # Run all due tasks concurrently
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        collected = {}
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                log.warning("Failed to collect %s: %s", key, result)
            else:
                collected[key] = result
                self._cached_data[key] = result
                self._mark(key)

        # Record to database
        try:
            if "agents_data" in collected:
                self.recorder.record_agents(collected["agents_data"])
            if "server_health" in collected:
                self.recorder.record_server(collected["server_health"])
            if "cron_jobs" in collected:
                self.recorder.record_cron(collected["cron_jobs"])
            if "security_status" in collected:
                self.recorder.record_security(collected["security_status"])
            if "network_activity" in collected:
                self.recorder.record_network(collected["network_activity"])
        except Exception as e:
            log.warning("Failed to record metrics: %s", e)

        sources = ", ".join(collected.keys())
        log.info("Collected: %s", sources)

        # ── GLACIAL tier: scan top failed SSH IPs ──
        if self._is_due("glacial_enrichment", TIER_GLACIAL):
            await self._glacial_enrichment(collected)
            self._mark("glacial_enrichment")

    async def _glacial_enrichment(self, collected):
        """DNS resolution, geolocation, and nmap scans for top failed SSH IPs."""
        ssh_summary = collected.get("ssh_login_summary",
                                     self._cached_data.get("ssh_login_summary",
                                                           {"accepted": [], "failed": []}))
        if not isinstance(ssh_summary, dict):
            return

        failed = ssh_summary.get("failed", [])
        if not failed:
            return

        log.info("Glacial: scanning top %d failed SSH IPs", min(len(failed), 5))
        scanned = 0
        for entry in failed[:5]:
            ip = entry.get("ip", "")
            if not ip:
                continue
            try:
                # DNS resolution (uses DB cache)
                hostname = await resolve_ip(ip, db=self.db)
                entry["hostname"] = hostname

                # Geolocation (uses DB cache)
                await get_ip_geolocation(ip, db=self.db)

                # Nmap scan of attacker (uses DB cache)
                result = await scan_attacker_ip(ip, db=self.db)
                scanned += 1
                ports = result.get("open_ports", "")
                log.info("  Scanned %s: ports=%s", ip, ports or "none")
            except Exception as e:
                log.warning("  Failed to scan %s: %s", ip, e)

        log.info("Glacial: scanned %d attacker IPs", scanned)

    async def run(self):
        """Main collection loop."""
        log.info("Collector daemon starting (fast=%ds, medium=%ds, slow=%ds)",
                 TIER_FAST, TIER_MEDIUM, TIER_SLOW)

        # Prune old data on startup
        try:
            self.db.prune()
            log.info("Database pruned")
        except Exception as e:
            log.warning("Prune failed: %s", e)

        # Force all collections on first run
        while self.running:
            try:
                await self.collect_once()
            except Exception as e:
                log.error("Collection cycle error: %s", e)

            # Sleep in small increments for responsive shutdown
            for _ in range(self.fast_interval):
                if not self.running:
                    break
                await asyncio.sleep(1)

        log.info("Collector daemon stopped")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GalacticCIC Data Collector")
    parser.add_argument("--interval", type=int, default=TIER_FAST,
                        help=f"Fast-tier collection interval (default: {TIER_FAST}s)")
    args = parser.parse_args()

    daemon = CollectorDaemon(fast_interval=args.interval)

    def handle_signal(signum, frame):
        log.info("Received signal %d, shutting down...", signum)
        daemon.running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    asyncio.run(daemon.run())


if __name__ == "__main__":
    main()
