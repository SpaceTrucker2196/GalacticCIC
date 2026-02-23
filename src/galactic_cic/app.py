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
    get_ssh_login_summary,
    resolve_ip,
    scan_attacker_ip,
    get_ip_geolocation,
    get_openclaw_logs,
    get_error_summary,
)
from galactic_cic.db.database import MetricsDB
from galactic_cic.db.recorder import MetricsRecorder
from galactic_cic.db.trends import TrendCalculator
from galactic_cic.panels.agents import AgentFleetPanel
from galactic_cic.panels.server import ServerHealthPanel
from galactic_cic.panels.cron import CronJobsPanel
from galactic_cic.panels.security import SecurityPanel
from galactic_cic.panels.activity import ActivityLogPanel


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
        Binding("Tab", "cycle_focus", "Cycle Focus"),
        Binding("?", "show_help", "Help"),
    ]

    # All refreshes unified to 30 seconds
    REFRESH_INTERVAL = 30

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
        ]

        # Color pair indices
        self.CP_NORMAL = 1
        self.CP_HIGHLIGHT = 2
        self.CP_WARN = 3
        self.CP_ERROR = 4
        self.CP_DIM = 5
        self.CP_HEADER = 6
        self.CP_FOOTER = 7

        # Background data refresh state
        self._last_refresh_time = 0.0
        self._refresh_lock = threading.Lock()
        self._refresh_thread = None
        self._force_refresh = True  # force on startup

    def _init_colors(self):
        """Set up curses color pairs for green phosphor theme."""
        curses.start_color()
        curses.use_default_colors()
        bg = curses.COLOR_BLACK
        curses.init_pair(self.CP_NORMAL, curses.COLOR_GREEN, bg)
        curses.init_pair(self.CP_HIGHLIGHT, curses.COLOR_GREEN, bg)
        curses.init_pair(self.CP_WARN, curses.COLOR_YELLOW, bg)
        curses.init_pair(self.CP_ERROR, curses.COLOR_RED, bg)
        curses.init_pair(self.CP_DIM, curses.COLOR_GREEN, bg)
        curses.init_pair(self.CP_HEADER, curses.COLOR_GREEN, bg)
        curses.init_pair(self.CP_FOOTER, curses.COLOR_GREEN, bg)

    def _color(self, pair_id):
        return curses.color_pair(pair_id)

    def _seconds_until_refresh(self):
        """Seconds until next refresh."""
        elapsed = time.monotonic() - self._last_refresh_time
        remaining = max(0, self.REFRESH_INTERVAL - elapsed)
        return int(remaining)

    def _draw_header(self):
        """Draw header with real-time clock and refresh countdown."""
        h, w = self.stdscr.getmaxyx()
        header_attr = self._color(self.CP_HEADER) | curses.A_BOLD

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
        footer_attr = self._color(self.CP_FOOTER)
        try:
            self.stdscr.addnstr(footer_y, 0, " " * w, w, footer_attr)
        except curses.error:
            pass
        keys = "q:Quit  r:Refresh  1-5:Panel  Tab:Cycle  ?:Help"
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
            "  1-5      Focus panel",
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
        attr = self._color(self.CP_HIGHLIGHT) | curses.A_BOLD
        try:
            self.stdscr.addnstr(start_y, start_x, "\u250c" + "\u2500" * (box_w - 2) + "\u2510", box_w, attr)
            for i, line in enumerate(help_lines):
                padded = f"\u2502 {line:<{box_w - 4}} \u2502"
                self.stdscr.addnstr(start_y + 1 + i, start_x, padded, box_w, attr)
            self.stdscr.addnstr(start_y + box_h - 1, start_x, "\u2514" + "\u2500" * (box_w - 2) + "\u2518", box_w, attr)
        except curses.error:
            pass

    def _layout_panels(self):
        h, w = self.stdscr.getmaxyx()
        content_y = 1
        content_h = h - 2
        if content_h < 6:
            return []
        row_h = content_h // 3
        bot_h = content_h - 2 * row_h
        half_w = w // 2
        right_w = w - half_w
        return [
            (0, content_y, 0, row_h, half_w),
            (1, content_y, half_w, row_h, right_w),
            (2, content_y + row_h, 0, row_h, half_w),
            (3, content_y + row_h, half_w, row_h, right_w),
            (4, content_y + 2 * row_h, 0, bot_h, w),
        ]

    def _draw_panels(self):
        layout = self._layout_panels()
        c_normal = self._color(self.CP_NORMAL)
        c_highlight = self._color(self.CP_HIGHLIGHT) | curses.A_BOLD
        c_warn = self._color(self.CP_WARN)
        c_error = self._color(self.CP_ERROR) | curses.A_BOLD
        c_dim = self._color(self.CP_DIM)
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
        """Refresh all panel data. Runs in background thread."""
        # Run all collectors concurrently
        results = await asyncio.gather(
            get_agents_data(),
            get_openclaw_status(),
            get_server_health(),
            get_cron_jobs(),
            get_security_status(),
            get_activity_log(),
            get_network_activity(),
            get_ssh_login_summary(),
            get_openclaw_logs(limit=20),
            get_error_summary(),
            return_exceptions=True,
        )

        # Unpack results (use empty dicts for failures)
        def safe(r, default=None):
            return r if not isinstance(r, Exception) else (default or {})

        agents_data = safe(results[0], {"agents": [], "error": "fetch failed"})
        status_data = safe(results[1], {"sessions": 0, "gateway_status": "unknown"})
        health = safe(results[2], {"cpu_percent": 0, "mem_percent": 0, "disk_percent": 0})
        cron_data = safe(results[3], {"jobs": []})
        security_data = safe(results[4], {})
        activity_events = safe(results[5], []) if not isinstance(results[5], Exception) else []
        network_data = safe(results[6], {"active_connections": 0, "connections": []})
        ssh_summary = safe(results[7], {"accepted": [], "failed": []})
        oc_logs = safe(results[8], []) if not isinstance(results[8], Exception) else []
        errors = safe(results[9], []) if not isinstance(results[9], Exception) else []

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

        # Historical sparkline data
        try:
            server_hist = self.db.get_recent_server_metrics(hours=1, limit=20)
            server_avgs = self.db.get_server_averages(hours=24)
            net_hist = self.db.get_recent_network_metrics(hours=1, limit=20)
            net_avg = self.db.get_network_average(hours=24)

            cpu_history = [row["cpu_percent"] for row in reversed(server_hist)]
            mem_history = [
                (row["mem_used_mb"] * 100.0 / row["mem_total_mb"])
                if row["mem_total_mb"] > 0 else 0
                for row in reversed(server_hist)
            ]
            disk_history = [
                (row["disk_used_gb"] * 100.0 / row["disk_total_gb"])
                if row["disk_total_gb"] > 0 else 0
                for row in reversed(server_hist)
            ]
            network_history = [row["active_connections"] for row in reversed(net_hist)]

            cpu_history.append(health.get("cpu_percent", 0))
            mem_history.append(health.get("mem_percent", 0))
            disk_history.append(health.get("disk_percent", 0))
            network_history.append(network_data.get("active_connections", 0))

            cpu_avg = server_avgs[0] if server_avgs and server_avgs[0] else None
            mem_avg = server_avgs[1] if server_avgs and server_avgs[1] else None
            disk_avg = server_avgs[2] if server_avgs and server_avgs[2] else None
        except Exception:
            cpu_history = mem_history = disk_history = network_history = []
            cpu_avg = mem_avg = disk_avg = net_avg = None

        # DNS + geolocation for SSH IPs (slower, but in background so OK)
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
            for entry in ssh_summary.get("failed", [])[:3]:
                ip = entry.get("ip", "")
                if ip:
                    attacker_scans[ip] = await scan_attacker_ip(ip, db=self.db)
        except Exception:
            pass

        # Top IPs for server panel
        try:
            top_ips = await get_top_ips(network_data, db=self.db)
        except Exception:
            top_ips = []

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
            )

            all_events = (activity_events if isinstance(activity_events, list) else []) + \
                         (oc_logs if isinstance(oc_logs, list) else [])
            all_events.sort(key=lambda e: e.get("time", ""), reverse=True)
            self.panels[4].update(all_events, errors=errors)

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
        elif key in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5")):
            self.focused_panel = key - ord("1")
        elif key == ord("\t"):
            self.focused_panel = (self.focused_panel + 1) % 5
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

        # Fill background
        h, w = stdscr.getmaxyx()
        bg = self._color(self.CP_NORMAL)
        try:
            for row in range(h):
                stdscr.addnstr(row, 0, " " * w, w, bg)
        except curses.error:
            pass

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
