"""GalacticCIC — Claw Information Center TUI (curses-based)."""

import asyncio
import curses
import locale
import time
import threading
from collections import namedtuple
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
    resolve_ip,
    scan_attacker_ip,
    get_ip_geolocation,
    get_openclaw_logs,
    get_error_summary,
    get_channels_status,
    get_update_status,
    build_action_items,
)
from galactic_cic.db.database import MetricsDB
from galactic_cic.db.recorder import MetricsRecorder
from galactic_cic.db.trends import TrendCalculator
from galactic_cic import theme
from galactic_cic.panels.agents import AgentFleetPanel
from galactic_cic.panels.server import ServerHealthPanel
from galactic_cic.panels.cron import CronJobsPanel
from galactic_cic.panels.security import SecurityPanel
from galactic_cic.panels.activity import ActivityLogPanel
from galactic_cic.panels.sitrep import SitrepPanel


Binding = namedtuple("Binding", ["key", "action", "description"])


class CICDashboard:
    """Main curses application for the CIC dashboard."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_all", "Refresh All"),
        Binding("1", "focus_panel_1", "Agent Fleet"),
        Binding("2", "focus_panel_2", "Server Health"),
        Binding("3", "focus_panel_3", "Cron Jobs"),
        Binding("4", "focus_panel_4", "Security"),
        Binding("5", "focus_panel_5", "Activity Log"),
        Binding("6", "focus_panel_6", "SITREP"),
        Binding("Tab", "cycle_focus", "Cycle Focus"),
        Binding("?", "show_help", "Help"),
    ]

    # Fast tier drives the display loop (30s countdown)
    REFRESH_INTERVAL = 30

    # Tiered refresh TTLs (seconds)
    TIER_FAST = 30       # server_health, top_processes
    TIER_MEDIUM = 120    # cron, activity, openclaw_logs, error_summary, network
    TIER_SLOW = 300      # agents, openclaw_status, security, ssh_login_summary
    TIER_GLACIAL = 900   # DNS resolution, geolocation, attacker scans

    def __init__(self):
        self.stdscr = None
        self.running = False
        self.show_help_overlay = False
        self.focused_panel = 0

        # Historical database
        self.db = MetricsDB()
        self.recorder = MetricsRecorder(self.db)
        self.trends = TrendCalculator(self.db)
        self.db.prune()

        # Panels
        self.panels = [
            AgentFleetPanel(),
            ServerHealthPanel(),
            CronJobsPanel(),
            SecurityPanel(),
            ActivityLogPanel(),
            SitrepPanel(),
        ]

        # Load theme from config
        theme.load_config()

        # Background data refresh state
        self._last_refresh_time = 0.0
        self._refresh_lock = threading.Lock()
        self._refresh_thread = None
        self._force_refresh = True  # force on startup

        # Tiered data collection state
        self._collection_timestamps = {}  # source_name -> monotonic timestamp
        self._cached_data = {}            # source_name -> last collected result
        self._force_all_tiers = True      # force all on startup

        # NMAP scanning flag (True while scans are active)
        self.nmap_scanning = False

        # Rolling in-memory sparkline histories (one entry per FAST refresh)
        self._cpu_history: list[float] = []
        self._mem_history: list[float] = []
        self._disk_history: list[float] = []
        self._net_history: list[int] = []
        self._HISTORY_MAX = 60

    def _init_colors(self):
        """Set up curses color pairs from theme system."""
        theme.init_colors()
        # Re-apply background after theme change to keep it black
        if self.stdscr:
            bg = theme.get_attr(theme.NORMAL)
            self.stdscr.bkgd(' ', bg)

    def _seconds_until_refresh(self):
        """Seconds until next refresh."""
        elapsed = time.monotonic() - self._last_refresh_time
        remaining = max(0, self.REFRESH_INTERVAL - elapsed)
        return int(remaining)

    def _draw_header(self):
        """Draw header with real-time clock and refresh countdown."""
        h, w = self.stdscr.getmaxyx()
        header_attr = theme.get_attr(theme.HEADER)

        try:
            self.stdscr.addnstr(0, 0, " " * w, w, header_attr)
        except curses.error:
            pass

        title = "CIC \u2014 Claw Information Center"
        try:
            self.stdscr.addnstr(0, 2, title, w - 4, header_attr)
        except curses.error:
            pass

        # Real-time dual timezone clock + refresh countdown
        now_utc = datetime.now(timezone.utc)
        utc_str = now_utc.strftime("%H:%M:%S UTC")
        try:
            from zoneinfo import ZoneInfo
            now_ct = now_utc.astimezone(ZoneInfo("America/Chicago"))
            ct_str = now_ct.strftime("%H:%M:%S CT")
        except Exception:
            ct_str = "??:??:?? CT"

        countdown = self._seconds_until_refresh()
        is_refreshing = self._refresh_thread is not None and self._refresh_thread.is_alive()
        if is_refreshing:
            status = "\u21bb"  # ↻ refreshing indicator
        else:
            status = f"{countdown}s"

        clock = f"{utc_str}  {ct_str}  [{status}]"
        clock_x = w - len(clock) - 2
        if clock_x > len(title) + 4:
            try:
                self.stdscr.addnstr(0, clock_x, clock, len(clock), header_attr)
            except curses.error:
                pass

    def _draw_footer(self):
        h, w = self.stdscr.getmaxyx()
        footer_y = h - 1
        footer_attr = theme.get_attr(theme.FOOTER)
        try:
            self.stdscr.addnstr(footer_y, 0, " " * w, w, footer_attr)
        except curses.error:
            pass
        keys = "q:Quit  r:Refresh  1-6:Panel  Tab:Cycle  t:Theme  ?:Help"
        try:
            self.stdscr.addnstr(footer_y, 2, keys, w - 4, footer_attr)
        except curses.error:
            pass

    def _draw_help_overlay(self):
        h, w = self.stdscr.getmaxyx()
        help_lines = [
            "GalacticCIC \u2014 Keyboard Controls",
            "",
            "  q        Quit",
            "  r        Refresh all panels",
            "  1-6      Focus panel",
            "  Tab      Cycle panel focus",
            "  ?        Toggle this help",
            "  Esc      Close help",
            "",
            f"  Refresh every {self.REFRESH_INTERVAL}s",
            "",
            "Press any key to close",
        ]
        box_w = max(len(line) for line in help_lines) + 4
        box_h = len(help_lines) + 2
        start_y = max(0, (h - box_h) // 2)
        start_x = max(0, (w - box_w) // 2)
        attr = theme.get_attr(theme.HIGHLIGHT)
        try:
            self.stdscr.addnstr(start_y, start_x, "\u250c" + "\u2500" * (box_w - 2) + "\u2510", box_w, attr)
            for i, line in enumerate(help_lines):
                padded = f"\u2502 {line:<{box_w - 4}} \u2502"
                self.stdscr.addnstr(start_y + 1 + i, start_x, padded, box_w, attr)
            self.stdscr.addnstr(start_y + box_h - 1, start_x, "\u2514" + "\u2500" * (box_w - 2) + "\u2518", box_w, attr)
        except curses.error:
            pass

    def _layout_panels(self):
        """Layout 6 panels in a 3-column grid.

        Wide (>=120 cols):
          [Agent Fleet]  [Server Health]  [SITREP]
          [Cron Jobs]    [Security]       (empty)
          [Activity Log — full width]

        Narrow (<120 cols): falls back to 2-column layout
          [Agent Fleet]  [Server Health]
          [Cron Jobs]    [Security]
          [Activity Log] [SITREP]
        """
        h, w = self.stdscr.getmaxyx()
        content_y = 1
        content_h = h - 2
        if content_h < 6:
            return []

        if w >= 120:
            # 3-column layout
            row_h = content_h // 3
            bot_h = content_h - 2 * row_h
            col_w = w // 3
            mid_w = w // 3
            right_w = w - col_w - mid_w
            return [
                (0, content_y, 0, row_h, col_w),              # Agent Fleet
                (1, content_y, col_w, row_h, mid_w),          # Server Health
                (5, content_y, col_w + mid_w, row_h, right_w),  # SITREP
                (2, content_y + row_h, 0, row_h, col_w),     # Cron Jobs
                (3, content_y + row_h, col_w, row_h, mid_w),  # Security
                (4, content_y + 2 * row_h, 0, bot_h, w),     # Activity Log
            ]
        else:
            # 2-column fallback
            row_h = content_h // 3
            bot_h = content_h - 2 * row_h
            half_w = w // 2
            right_w = w - half_w
            return [
                (0, content_y, 0, row_h, half_w),
                (1, content_y, half_w, row_h, right_w),
                (2, content_y + row_h, 0, row_h, half_w),
                (3, content_y + row_h, half_w, row_h, right_w),
                (4, content_y + 2 * row_h, 0, bot_h, half_w),
                (5, content_y + 2 * row_h, half_w, bot_h, right_w),
            ]

    def _draw_panels(self):
        layout = self._layout_panels()
        c_normal = theme.get_attr(theme.NORMAL)
        c_highlight = theme.get_attr(theme.HIGHLIGHT)
        c_warn = theme.get_attr(theme.WARNING)
        c_error = theme.get_attr(theme.ERROR)
        c_dim = theme.get_attr(theme.DIM)
        for idx, y, x, height, width in layout:
            panel = self.panels[idx]
            panel.focused = (idx == self.focused_panel)
            panel.draw(self.stdscr, y, x, height, width, c_normal, c_highlight, c_warn, c_error, c_dim)

    def _do_background_refresh(self):
        """Run data collection in a background thread using its own event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._refresh_all_data())
            loop.close()
        except Exception:
            pass  # Don't crash the UI thread on data errors
        finally:
            self._last_refresh_time = time.monotonic()

    async def _refresh_all_data(self):
        """Refresh panel data using tiered collection.

        Only collectors whose TTL has expired are re-run. Cached results
        from the previous collection are reused for sources that are still
        fresh. On startup (or manual 'r'), all tiers are forced.
        """
        now = time.monotonic()
        force_all = self._force_all_tiers
        self._force_all_tiers = False

        def is_due(source, ttl):
            if force_all:
                return True
            return (now - self._collection_timestamps.get(source, 0)) >= ttl

        # ── Build task list for due sources ──
        tasks = {}

        # FAST tier (30s) — lightweight, changes often
        if is_due("server_health", self.TIER_FAST):
            tasks["server_health"] = get_server_health()
        if is_due("top_processes", self.TIER_FAST):
            tasks["top_processes"] = get_top_processes()

        # MEDIUM tier (2 min) — moderate cost
        if is_due("cron_jobs", self.TIER_MEDIUM):
            tasks["cron_jobs"] = get_cron_jobs()
        if is_due("activity_log", self.TIER_MEDIUM):
            tasks["activity_log"] = get_activity_log()
        if is_due("openclaw_logs", self.TIER_MEDIUM):
            tasks["openclaw_logs"] = get_openclaw_logs(limit=20)
        if is_due("error_summary", self.TIER_MEDIUM):
            tasks["error_summary"] = get_error_summary()
        if is_due("network_activity", self.TIER_MEDIUM):
            tasks["network_activity"] = get_network_activity()

        # SLOW tier (5 min) — expensive, rarely changes
        if is_due("agents_data", self.TIER_SLOW):
            tasks["agents_data"] = get_agents_data()
        if is_due("openclaw_status", self.TIER_SLOW):
            tasks["openclaw_status"] = get_openclaw_status()
        nmap_in_slow = is_due("security_status", self.TIER_SLOW)
        if nmap_in_slow:
            self.nmap_scanning = True
            tasks["security_status"] = get_security_status()
        if is_due("ssh_login_summary", self.TIER_SLOW):
            tasks["ssh_login_summary"] = get_ssh_login_summary()
        if is_due("channels_status", self.TIER_SLOW):
            tasks["channels_status"] = get_channels_status()
        if is_due("update_status", self.TIER_SLOW):
            tasks["update_status"] = get_update_status()

        # ── Run all due tasks concurrently ──
        if tasks:
            keys = list(tasks.keys())
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for key, result in zip(keys, results):
                if not isinstance(result, Exception):
                    self._cached_data[key] = result
                self._collection_timestamps[key] = now
            if nmap_in_slow:
                self.nmap_scanning = False

        # ── Read from cache (with safe defaults) ──
        def cached(key, default):
            return self._cached_data.get(key, default)

        agents_data = cached("agents_data", {"agents": [], "error": "fetch failed"})
        status_data = cached("openclaw_status", {"sessions": 0, "gateway_status": "unknown"})
        health = cached("server_health", {"cpu_percent": 0, "mem_percent": 0, "disk_percent": 0})
        cron_data = cached("cron_jobs", {"jobs": []})
        security_data = cached("security_status", {})
        activity_events = cached("activity_log", [])
        if not isinstance(activity_events, list):
            activity_events = []
        network_data = cached("network_activity", {"active_connections": 0, "connections": []})
        ssh_summary = cached("ssh_login_summary", {"accepted": [], "failed": []})
        oc_logs = cached("openclaw_logs", [])
        if not isinstance(oc_logs, list):
            oc_logs = []
        errors = cached("error_summary", [])
        if not isinstance(errors, list):
            errors = []
        processes = cached("top_processes", [])
        if not isinstance(processes, list):
            processes = []
        channels = cached("channels_status", [])
        if not isinstance(channels, list):
            channels = []
        update_info = cached("update_status", {"available": False, "current": "", "latest": ""})

        # Record metrics to DB
        try:
            self.recorder.record_agents(agents_data)
            self.recorder.record_server(health)
            self.recorder.record_cron(cron_data)
            self.recorder.record_security(security_data)
            self.recorder.record_network(network_data)
        except Exception:
            pass

        # Get trends and historical data
        try:
            tokens_per_hour = self.trends.get_agent_tokens_per_hour()
            server_trends = self.trends.get_server_trends()
        except Exception:
            tokens_per_hour = {}
            server_trends = {}

        # Rolling in-memory sparkline data — append on every refresh
        self._cpu_history.append(health.get("cpu_percent", 0))
        self._mem_history.append(health.get("mem_percent", 0))
        self._disk_history.append(health.get("disk_percent", 0))
        self._net_history.append(network_data.get("active_connections", 0))
        # Trim to max length
        if len(self._cpu_history) > self._HISTORY_MAX:
            self._cpu_history = self._cpu_history[-self._HISTORY_MAX:]
        if len(self._mem_history) > self._HISTORY_MAX:
            self._mem_history = self._mem_history[-self._HISTORY_MAX:]
        if len(self._disk_history) > self._HISTORY_MAX:
            self._disk_history = self._disk_history[-self._HISTORY_MAX:]
        if len(self._net_history) > self._HISTORY_MAX:
            self._net_history = self._net_history[-self._HISTORY_MAX:]

        cpu_history = list(self._cpu_history)
        mem_history = list(self._mem_history)
        disk_history = list(self._disk_history)
        network_history = list(self._net_history)

        try:
            server_avgs = self.db.get_server_averages(hours=24)
            net_avg = self.db.get_network_average(hours=24)
            cpu_avg = server_avgs[0] if server_avgs and server_avgs[0] else None
            mem_avg = server_avgs[1] if server_avgs and server_avgs[1] else None
            disk_avg = server_avgs[2] if server_avgs and server_avgs[2] else None
        except Exception:
            cpu_avg = mem_avg = disk_avg = net_avg = None

        # ── GLACIAL tier: DNS + geolocation + attacker scans ──
        glacial_due = is_due("glacial_enrichment", self.TIER_GLACIAL)

        if glacial_due:
            geo_data = {}
            attacker_scans = {}
            try:
                all_ips = set()
                for entry_list in (ssh_summary.get("accepted", []), ssh_summary.get("failed", [])):
                    for entry in entry_list:
                        ip = entry.get("ip", "")
                        if ip:
                            entry["hostname"] = await resolve_ip(ip, db=self.db)
                            all_ips.add(ip)
                for ip in all_ips:
                    geo_data[ip] = await get_ip_geolocation(ip, db=self.db)
                self.nmap_scanning = True
                for entry in ssh_summary.get("failed", [])[:3]:
                    ip = entry.get("ip", "")
                    if ip:
                        attacker_scans[ip] = await scan_attacker_ip(ip, db=self.db)
                self.nmap_scanning = False
            except Exception:
                self.nmap_scanning = False
            self._cached_data["geo_data"] = geo_data
            self._cached_data["attacker_scans"] = attacker_scans
            self._collection_timestamps["glacial_enrichment"] = now
        else:
            geo_data = cached("geo_data", {})
            attacker_scans = cached("attacker_scans", {})

        # Top IPs for server panel (uses resolve_ip with its own 24h DB cache)
        try:
            top_ips = await get_top_ips(network_data, db=self.db)
        except Exception:
            top_ips = []

        # Build external IP summary for activity panel
        ext_ip_summary = cached("ext_ip_summary", [])
        if glacial_due:
            try:
                all_external = set()
                # From network connections
                for ip in network_data.get("peer_ips", {}):
                    if ip and not ip.startswith("127.") and ip != "::1":
                        all_external.add(ip)
                # From SSH logs
                for entry_list in (ssh_summary.get("accepted", []),
                                   ssh_summary.get("failed", [])):
                    for entry in entry_list:
                        ip = entry.get("ip", "")
                        if ip:
                            all_external.add(ip)

                summary = []
                for ip in sorted(all_external):
                    hostname = await resolve_ip(ip, db=self.db)
                    geo = geo_data.get(ip) or await get_ip_geolocation(ip, db=self.db)
                    scan = attacker_scans.get(ip) or await scan_attacker_ip(ip, db=self.db)
                    summary.append({
                        "ip": ip,
                        "hostname": hostname,
                        "country": geo.get("country_code", "?"),
                        "ports": scan.get("open_ports", ""),
                    })
                ext_ip_summary = summary
                self._cached_data["ext_ip_summary"] = ext_ip_summary
            except Exception:
                pass

        # Update panels (thread-safe since Python GIL protects attribute assignment)
        with self._refresh_lock:
            self.panels[0].update(agents_data, status_data, tokens_per_hour)
            self.panels[1].update(
                health, server_trends,
                network_history=network_history,
                network_current=network_data.get("active_connections", 0),
                top_ips=top_ips,
                cpu_history=cpu_history,
                mem_history=mem_history,
                disk_history=disk_history,
                cpu_avg=cpu_avg,
                mem_avg=mem_avg,
                disk_avg=disk_avg,
                net_avg=net_avg,
                processes=processes,
            )
            self.panels[2].update(cron_data)

            last_scan = None
            try:
                last_scan = self.db.fetchone(
                    "SELECT timestamp FROM port_scans ORDER BY timestamp DESC LIMIT 1"
                )
            except Exception:
                pass
            last_nmap_time = ""
            if last_scan:
                last_nmap_time = datetime.fromtimestamp(
                    last_scan["timestamp"]
                ).strftime("%H:%M:%S")

            self.panels[3].update(
                security_data, ssh_summary=ssh_summary,
                last_nmap_time=last_nmap_time,
                attacker_scans=attacker_scans,
                geo_data=geo_data,
                nmap_scanning=self.nmap_scanning,
            )

            all_events = (activity_events if isinstance(activity_events, list) else []) + \
                         (oc_logs if isinstance(oc_logs, list) else [])
            all_events.sort(key=lambda e: e.get("time", ""), reverse=True)
            self.panels[4].update(all_events, errors=errors,
                                  ext_ip_summary=ext_ip_summary)

            # SITREP panel — channels, update, action items
            action_items = build_action_items(
                cron_data, security_data, channels, update_info, health,
            )
            self.panels[5].update(
                channels=channels,
                update_info=update_info,
                action_items=action_items,
            )

    def _maybe_start_refresh(self):
        """Start background refresh if interval elapsed or forced."""
        now = time.monotonic()
        thread_alive = self._refresh_thread is not None and self._refresh_thread.is_alive()

        if thread_alive:
            return  # Already refreshing

        should_refresh = self._force_refresh or (now - self._last_refresh_time) >= self.REFRESH_INTERVAL

        if should_refresh:
            self._force_refresh = False
            self._refresh_thread = threading.Thread(
                target=self._do_background_refresh,
                daemon=True,
            )
            self._refresh_thread.start()

    def _handle_key(self, key):
        if key == ord("q"):
            return False
        elif key == ord("r"):
            self._force_refresh = True
            self._force_all_tiers = True
        elif key in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6")):
            self.focused_panel = key - ord("1")
        elif key == ord("\t"):
            self.focused_panel = (self.focused_panel + 1) % 6
        elif key == ord("t"):
            theme.cycle_theme()
            self._init_colors()
        elif key == ord("?"):
            self.show_help_overlay = not self.show_help_overlay
        elif key == 27:
            self.show_help_overlay = False
        elif self.show_help_overlay:
            self.show_help_overlay = False
        return True

    def _main_loop(self, stdscr):
        """Main UI loop — redraws at ~10fps, data refreshes in background."""
        self.stdscr = stdscr
        self.running = True

        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)  # 100ms = ~10fps for smooth clock

        self._init_colors()

        # Force black background — set the window background attribute
        bg = theme.get_attr(theme.NORMAL)
        stdscr.bkgd(' ', bg)
        stdscr.clear()

        while self.running:
            # Handle input
            try:
                key = stdscr.getch()
            except curses.error:
                key = -1

            if key != -1:
                if not self._handle_key(key):
                    break

            # Start background data refresh if needed
            self._maybe_start_refresh()

            # Redraw UI (always — clock updates every frame)
            stdscr.erase()
            self._draw_header()
            with self._refresh_lock:
                self._draw_panels()
            self._draw_footer()

            if self.show_help_overlay:
                self._draw_help_overlay()

            stdscr.refresh()
            # Sleep briefly for ~10fps (100ms timeout on getch handles this)

    def run(self):
        """Start the curses application."""
        locale.setlocale(locale.LC_ALL, "")
        curses.wrapper(self._main_loop)


def main():
    """Entry point for console_scripts."""
    app = CICDashboard()
    app.run()


if __name__ == "__main__":
    main()
