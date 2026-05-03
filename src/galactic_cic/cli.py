"""
gcic — CLI for GalacticCIC operations dashboard.

Commands:
    gcic start        Start the collector daemon
    gcic stop         Stop the collector daemon
    gcic restart      Restart the collector daemon
    gcic status       Show collector daemon status + DB stats
    gcic dashboard    Launch the TUI dashboard
    gcic collect      Run a single collection cycle
    gcic db           Show database statistics
    gcic db prune     Prune old records
    gcic db path      Print database file path
    gcic logs         Show collector daemon logs
    gcic version      Show version
"""

import argparse
import json
import os
import subprocess
import sys
import time

SERVICE_NAME = "galactic-cic-collector.service"
LAUNCHD_LABEL = "ai.openclaw.galactic-cic-collector"
DB_PATH = os.path.expanduser("~/.galactic_cic/metrics.db")
COLLECTOR_LOG = os.path.expanduser("~/.galactic_cic/collector.log")
COLLECTOR_ERR = os.path.expanduser("~/.galactic_cic/collector.err")
LAUNCHD_PLIST = os.path.expanduser(
    f"~/Library/LaunchAgents/{LAUNCHD_LABEL}.plist"
)
IS_DARWIN = sys.platform == "darwin"


def _systemctl(*args):
    """Run systemctl --user command, return (stdout, returncode)."""
    cmd = ["systemctl", "--user"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


def _launchctl(*args):
    """Run launchctl command, return (stdout, returncode)."""
    r = subprocess.run(["launchctl", *args], capture_output=True, text=True)
    return r.stdout.strip(), r.returncode


def _launchctl_list_entry():
    """Return (pid, last_exit_code) for the launchd job, or (None, None)."""
    out, rc = _launchctl("list", LAUNCHD_LABEL)
    if rc != 0:
        return None, None
    pid = None
    last = None
    for line in out.splitlines():
        line = line.strip().rstrip(";").rstrip(",")
        if line.startswith('"PID"'):
            try:
                pid = int(line.split("=", 1)[1].strip())
            except ValueError:
                pid = None
        elif line.startswith('"LastExitStatus"'):
            try:
                last = int(line.split("=", 1)[1].strip())
            except ValueError:
                last = None
    return pid, last


def _is_running():
    """Check if collector daemon is running."""
    if IS_DARWIN:
        pid, _ = _launchctl_list_entry()
        return pid is not None and pid > 0
    out, _ = _systemctl("is-active", SERVICE_NAME)
    return out == "active"


def cmd_start(args):
    """Start the collector daemon."""
    if _is_running():
        print("Collector is already running")
        cmd_status(args)
        return
    if IS_DARWIN:
        if not os.path.exists(LAUNCHD_PLIST):
            print("✖ launchd agent not installed")
            print("  Run: gcic install")
            return
        _launchctl("load", LAUNCHD_PLIST)
    else:
        _systemctl("start", SERVICE_NAME)
    time.sleep(1)
    if _is_running():
        print("✓ Collector started")
    else:
        print("✖ Failed to start collector")
        if not IS_DARWIN:
            out, _ = _systemctl("status", SERVICE_NAME)
            print(out)


def cmd_stop(args):
    """Stop the collector daemon."""
    if not _is_running():
        print("Collector is not running")
        return
    if IS_DARWIN:
        _launchctl("unload", LAUNCHD_PLIST)
    else:
        _systemctl("stop", SERVICE_NAME)
    time.sleep(1)
    if not _is_running():
        print("✓ Collector stopped")
    else:
        print("✖ Failed to stop collector")


def cmd_restart(args):
    """Restart the collector daemon."""
    if IS_DARWIN:
        # kickstart -k restarts the running job; falls back to load if not loaded
        _, rc = _launchctl(
            "kickstart", "-k", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"
        )
        if rc != 0 and os.path.exists(LAUNCHD_PLIST):
            _launchctl("load", LAUNCHD_PLIST)
    else:
        _systemctl("restart", SERVICE_NAME)
    time.sleep(1)
    if _is_running():
        print("✓ Collector restarted")
    else:
        print("✖ Failed to restart collector")
        if not IS_DARWIN:
            out, _ = _systemctl("status", SERVICE_NAME)
            print(out)


def cmd_status(args):
    """Show collector daemon status and DB stats."""
    if IS_DARWIN:
        pid, last_exit = _launchctl_list_entry()
        if pid is None:
            if os.path.exists(LAUNCHD_PLIST):
                print("  Collector:  ✖ NOT LOADED (plist installed)")
                print("  Start:      gcic start")
            else:
                print("  Collector:  ✖ NOT INSTALLED")
                print("  Install:    gcic install")
            return
        if pid > 0:
            print(f"  Collector:  ● RUNNING (PID {pid})")
            print(f"  Plist:      {LAUNCHD_PLIST}")
        else:
            print(f"  Collector:  ✖ STOPPED (last exit {last_exit})")
            print(f"  Plist:      {LAUNCHD_PLIST}")
            return
    else:
        if _is_running():
            out, _ = _systemctl(
                "show", SERVICE_NAME,
                "--property=MainPID,ActiveEnterTimestamp,MemoryCurrent",
            )
            props = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k] = v
            pid = props.get("MainPID", "?")
            since = props.get("ActiveEnterTimestamp", "?")
            mem = props.get("MemoryCurrent", "?")
            if mem.isdigit():
                mem = f"{int(mem) / 1024 / 1024:.1f}MB"
            print(f"  Collector:  ● RUNNING (PID {pid})")
            print(f"  Since:      {since}")
            print(f"  Memory:     {mem}")
        else:
            out, _ = _systemctl("list-unit-files", SERVICE_NAME)
            if SERVICE_NAME in out:
                print("  Collector:  ✖ STOPPED (service installed)")
            else:
                print("  Collector:  ✖ NOT INSTALLED")
                print("  Install:    gcic install")
            return

    # DB stats
    print()
    _print_db_stats()


def cmd_dashboard(args):
    """Launch the TUI dashboard."""
    from galactic_cic.app import main
    main()


def cmd_collect(args):
    """Run a single collection cycle."""
    import asyncio
    from galactic_cic.collector_daemon import CollectorDaemon

    print("Running single collection cycle...")
    daemon = CollectorDaemon()

    async def once():
        # Force all tiers
        daemon._timestamps.clear()
        await daemon.collect_once()

    asyncio.run(once())
    print("✓ Collection complete")
    _print_db_stats()


def cmd_db(args):
    """Database operations."""
    if args.db_action == "prune":
        from galactic_cic.db.database import MetricsDB
        db = MetricsDB()
        db.prune()
        print("✓ Database pruned")
        _print_db_stats()
    elif args.db_action == "path":
        print(DB_PATH)
    else:
        _print_db_stats()


def _print_db_stats():
    """Print database statistics."""
    if not os.path.exists(DB_PATH):
        print("  Database:   not found")
        return

    import sqlite3
    size_mb = os.path.getsize(DB_PATH) / 1024 / 1024
    print(f"  Database:   {DB_PATH} ({size_mb:.1f}MB)")

    try:
        conn = sqlite3.connect(DB_PATH)
        tables = {
            "server_metrics": "Server",
            "agent_metrics": "Agents",
            "cron_metrics": "Cron",
            "security_metrics": "Security",
            "network_metrics": "Network",
            "dns_cache": "DNS cache",
            "attacker_scans": "Attacker scans",
            "geo_cache": "Geolocation",
            "sitrep_cache": "SITREP",
        }
        for table, label in tables.items():
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                count = row[0] if row else 0
                # Get newest timestamp if available
                try:
                    ts_row = conn.execute(
                        f"SELECT MAX(timestamp) FROM {table}"
                    ).fetchone()
                    if ts_row and ts_row[0]:
                        from datetime import datetime
                        newest = datetime.fromtimestamp(ts_row[0]).strftime("%H:%M:%S")
                        print(f"  {label + ':':<18} {count:>6} records  (latest: {newest})")
                    else:
                        print(f"  {label + ':':<18} {count:>6} records")
                except Exception:
                    print(f"  {label + ':':<18} {count:>6} records")
            except Exception:
                pass
        conn.close()
    except Exception as e:
        print(f"  Error reading DB: {e}")


def cmd_logs(args):
    """Show collector daemon logs."""
    count = args.lines or 30
    if IS_DARWIN:
        # On macOS we tail the file logs written by the launchd agent.
        # Prefer collector.err since the daemon logs INFO-level there.
        log_file = COLLECTOR_ERR if os.path.exists(COLLECTOR_ERR) else COLLECTOR_LOG
        if not os.path.exists(log_file):
            print(f"✖ No log file at {log_file}")
            print("  Is the collector installed? Run: gcic install")
            return
        cmd = ["tail", "-n", str(count)]
        if args.follow:
            cmd.append("-f")
        cmd.append(log_file)
        os.execvp("tail", cmd)
    cmd = ["journalctl", "--user", "-u", SERVICE_NAME,
           "--no-pager", "-n", str(count)]
    if args.follow:
        cmd.append("-f")
    os.execvp("journalctl", cmd)


def _install_launchd():
    """Install the macOS launchd user agent."""
    collector_bin = subprocess.run(
        ["which", "galactic-cic-collector"],
        capture_output=True, text=True,
    ).stdout.strip()
    if not collector_bin:
        print("✖ galactic-cic-collector not found in PATH")
        print("  Run: pip install -e .")
        return

    home = os.path.expanduser("~")
    plist_dir = os.path.dirname(LAUNCHD_PLIST)
    os.makedirs(plist_dir, exist_ok=True)
    os.makedirs(os.path.dirname(COLLECTOR_LOG), exist_ok=True)

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{collector_bin}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>WorkingDirectory</key>
    <string>{home}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>{home}</string>
    </dict>
    <key>StandardOutPath</key>
    <string>{COLLECTOR_LOG}</string>
    <key>StandardErrorPath</key>
    <string>{COLLECTOR_ERR}</string>
</dict>
</plist>
"""
    # Unload any existing copy before overwriting (best-effort).
    if os.path.exists(LAUNCHD_PLIST):
        _launchctl("unload", LAUNCHD_PLIST)
    with open(LAUNCHD_PLIST, "w") as f:
        f.write(plist_content)
    _launchctl("load", LAUNCHD_PLIST)
    print(f"✓ launchd agent installed at {LAUNCHD_PLIST}")
    print(f"  Collector: {collector_bin}")
    print("  Status:    gcic status")


def cmd_install(args):
    """Install/reinstall the collector service for the current platform."""
    if IS_DARWIN:
        _install_launchd()
        return

    service_dir = os.path.expanduser("~/.config/systemd/user")
    service_path = os.path.join(service_dir, SERVICE_NAME)
    os.makedirs(service_dir, exist_ok=True)

    # Find the collector binary
    collector_bin = subprocess.run(
        ["which", "galactic-cic-collector"],
        capture_output=True, text=True
    ).stdout.strip()

    if not collector_bin:
        print("✖ galactic-cic-collector not found in PATH")
        print("  Run: pip install -e . --break-system-packages")
        return

    # Get current PATH for nvm etc
    nvm_bin = os.path.expanduser("~/.nvm/versions/node/v24.13.0/bin")
    local_bin = os.path.expanduser("~/.local/bin")
    path_dirs = f"{nvm_bin}:{local_bin}:/usr/local/bin:/usr/bin:/bin"

    service_content = f"""[Unit]
Description=GalacticCIC Data Collector
After=default.target

[Service]
Type=simple
Environment=PATH={path_dirs}
ExecStart={collector_bin} --interval 30
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
    with open(service_path, "w") as f:
        f.write(service_content)

    _systemctl("daemon-reload")
    _systemctl("enable", SERVICE_NAME)
    print(f"✓ Service installed at {service_path}")
    print(f"  Collector: {collector_bin}")
    print(f"  Run: gcic start")


def cmd_version(args):
    """Show version."""
    print("galactic-cic 3.1.0")


def main():
    parser = argparse.ArgumentParser(
        prog="gcic",
        description="GalacticCIC — Claw Information Center CLI",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    sub.add_parser("start", help="Start the collector daemon")
    sub.add_parser("stop", help="Stop the collector daemon")
    sub.add_parser("restart", help="Restart the collector daemon")
    sub.add_parser("status", help="Show collector status + DB stats")
    sub.add_parser("dashboard", help="Launch the TUI dashboard")
    sub.add_parser("collect", help="Run a single collection cycle")
    sub.add_parser("install", help="Install/reinstall systemd service")
    sub.add_parser("version", help="Show version")

    db_parser = sub.add_parser("db", help="Database operations")
    db_parser.add_argument("db_action", nargs="?", default="stats",
                           choices=["stats", "prune", "path"],
                           help="DB action (default: stats)")

    logs_parser = sub.add_parser("logs", help="Show collector logs")
    logs_parser.add_argument("-n", "--lines", type=int, default=30,
                             help="Number of lines (default: 30)")
    logs_parser.add_argument("-f", "--follow", action="store_true",
                             help="Follow log output")

    args = parser.parse_args()

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "dashboard": cmd_dashboard,
        "collect": cmd_collect,
        "db": cmd_db,
        "logs": cmd_logs,
        "install": cmd_install,
        "version": cmd_version,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
