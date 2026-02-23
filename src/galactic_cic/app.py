"""GalacticCIC — Claw Information Center TUI (curses-based)."""

import asyncio
import curses
import locale
import time
from collections import namedtuple
from datetime import datetime, timezone

from galactic_cic.data.collectors import (
    get_agents_data,
    get_openclaw_status,
    get_server_health,
    get_cron_jobs,
    get_security_status,
    get_activity_log,
)
from galactic_cic.panels.agents import AgentFleetPanel
from galactic_cic.panels.server import ServerHealthPanel
from galactic_cic.panels.cron import CronJobsPanel
from galactic_cic.panels.security import SecurityPanel
from galactic_cic.panels.activity import ActivityLogPanel


# Binding namedtuple compatible with test assertions
Binding = namedtuple("Binding", ["key", "action", "description"])


class CICDashboard:
    """Main curses application for the CIC dashboard."""

    # Keyboard bindings — tests inspect this list
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

    # Auto-refresh intervals (seconds)
    REFRESH_SERVER = 5
    REFRESH_AGENTS = 30
    REFRESH_CRON = 30
    REFRESH_SECURITY = 60
    REFRESH_ACTIVITY = 10

    def __init__(self):
        self.stdscr = None
        self.running = False
        self.show_help_overlay = False
        self.focused_panel = 0  # 0-4

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

        # Last refresh timestamps
        self._last_refresh = {
            "server": 0.0,
            "agents": 0.0,
            "cron": 0.0,
            "security": 0.0,
            "activity": 0.0,
        }

    def _init_colors(self):
        """Set up curses color pairs for green phosphor theme."""
        curses.start_color()
        curses.use_default_colors()

        if curses.can_change_color():
            # Background: near-black dark green (#020a02)
            curses.init_color(16, 8, 40, 8)
            # Normal green (#33ff33)
            curses.init_color(17, 200, 1000, 200)
            # Bright green / highlight (#00ff00)
            curses.init_color(18, 0, 1000, 0)
            # Dim green / labels (#0d7a0d)
            curses.init_color(19, 52, 480, 52)
            # Orange / warnings (#ff8800)
            curses.init_color(20, 1000, 533, 0)
            # Red / errors (#cc3333)
            curses.init_color(21, 800, 200, 200)
            # Header bright green (#4aff4a)
            curses.init_color(22, 290, 1000, 290)

            bg = 16
            curses.init_pair(self.CP_NORMAL, 17, bg)
            curses.init_pair(self.CP_HIGHLIGHT, 18, bg)
            curses.init_pair(self.CP_WARN, 20, bg)
            curses.init_pair(self.CP_ERROR, 21, bg)
            curses.init_pair(self.CP_DIM, 19, bg)
            curses.init_pair(self.CP_HEADER, 22, bg)
            curses.init_pair(self.CP_FOOTER, 19, bg)
        else:
            # Fallback for terminals that can't redefine colors
            curses.init_pair(self.CP_NORMAL, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(self.CP_HIGHLIGHT, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(self.CP_WARN, curses.COLOR_MAGENTA, curses.COLOR_BLACK)  # closest to orange in 8-color
            curses.init_pair(self.CP_ERROR, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(self.CP_DIM, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(self.CP_HEADER, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(self.CP_FOOTER, curses.COLOR_GREEN, curses.COLOR_BLACK)

    def _color(self, pair_id):
        """Get curses color pair attribute."""
        return curses.color_pair(pair_id)

    def _draw_header(self):
        """Draw the header bar with title and dual timezone clock."""
        h, w = self.stdscr.getmaxyx()
        header_attr = self._color(self.CP_HEADER) | curses.A_BOLD

        # Clear header line
        try:
            self.stdscr.addnstr(0, 0, " " * w, w, header_attr)
        except curses.error:
            pass

        title = "CIC \u2014 Claw Information Center"
        try:
            self.stdscr.addnstr(0, 2, title, w - 4, header_attr)
        except curses.error:
            pass

        # Dual timezone clock
        now_utc = datetime.now(timezone.utc)
        utc_str = now_utc.strftime("%H:%M:%S UTC")
        try:
            from zoneinfo import ZoneInfo
            now_ct = now_utc.astimezone(ZoneInfo("America/Chicago"))
            ct_str = now_ct.strftime("%H:%M:%S CT")
        except Exception:
            ct_str = "??:??:?? CT"

        clock = f"{utc_str}  {ct_str}"
        clock_x = w - len(clock) - 2
        if clock_x > len(title) + 4:
            try:
                self.stdscr.addnstr(0, clock_x, clock, len(clock), header_attr)
            except curses.error:
                pass

    def _draw_footer(self):
        """Draw the footer bar with keybindings."""
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
        """Draw help overlay in center of screen."""
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
            "Auto-Refresh Intervals:",
            "  Server health    5s",
            "  Agents / Cron   30s",
            "  Security        60s",
            "  Activity log    10s",
            "",
            "Press any key to close",
        ]

        box_w = max(len(line) for line in help_lines) + 4
        box_h = len(help_lines) + 2
        start_y = max(0, (h - box_h) // 2)
        start_x = max(0, (w - box_w) // 2)

        attr = self._color(self.CP_HIGHLIGHT) | curses.A_BOLD

        try:
            self.stdscr.addnstr(
                start_y, start_x,
                "\u250c" + "\u2500" * (box_w - 2) + "\u2510",
                box_w, attr,
            )
            for i, line in enumerate(help_lines):
                padded = f"\u2502 {line:<{box_w - 4}} \u2502"
                self.stdscr.addnstr(start_y + 1 + i, start_x, padded, box_w, attr)
            self.stdscr.addnstr(
                start_y + box_h - 1, start_x,
                "\u2514" + "\u2500" * (box_w - 2) + "\u2518",
                box_w, attr,
            )
        except curses.error:
            pass

    def _layout_panels(self):
        """Calculate panel positions based on terminal size.

        Layout:
          Row 1: [Agent Fleet] [Server Health]
          Row 2: [Cron Jobs]   [Security]
          Row 3: [Activity Log — full width]
        """
        h, w = self.stdscr.getmaxyx()

        content_y = 1           # below header
        content_h = h - 2       # minus header + footer
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
        """Draw all panels in their layout positions."""
        layout = self._layout_panels()
        c_normal = self._color(self.CP_NORMAL)
        c_highlight = self._color(self.CP_HIGHLIGHT) | curses.A_BOLD
        c_warn = self._color(self.CP_WARN)
        c_error = self._color(self.CP_ERROR) | curses.A_BOLD
        c_dim = self._color(self.CP_DIM)

        for idx, y, x, height, width in layout:
            panel = self.panels[idx]
            panel.focused = (idx == self.focused_panel)
            panel.draw(
                self.stdscr, y, x, height, width,
                c_normal, c_highlight, c_warn, c_error, c_dim,
            )

    async def _refresh_data(self, force=False):
        """Refresh panel data based on intervals."""
        now = time.monotonic()
        tasks = []

        if force or (now - self._last_refresh["agents"]) >= self.REFRESH_AGENTS:
            tasks.append(self._refresh_agents())
            self._last_refresh["agents"] = now

        if force or (now - self._last_refresh["server"]) >= self.REFRESH_SERVER:
            tasks.append(self._refresh_server())
            self._last_refresh["server"] = now

        if force or (now - self._last_refresh["cron"]) >= self.REFRESH_CRON:
            tasks.append(self._refresh_cron())
            self._last_refresh["cron"] = now

        if force or (now - self._last_refresh["security"]) >= self.REFRESH_SECURITY:
            tasks.append(self._refresh_security())
            self._last_refresh["security"] = now

        if force or (now - self._last_refresh["activity"]) >= self.REFRESH_ACTIVITY:
            tasks.append(self._refresh_activity())
            self._last_refresh["activity"] = now

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _refresh_agents(self):
        agents_data = await get_agents_data()
        status_data = await get_openclaw_status()
        self.panels[0].update(agents_data, status_data)

    async def _refresh_server(self):
        health = await get_server_health()
        self.panels[1].update(health)

    async def _refresh_cron(self):
        cron_data = await get_cron_jobs()
        self.panels[2].update(cron_data)

    async def _refresh_security(self):
        security_data = await get_security_status()
        self.panels[3].update(security_data)

    async def _refresh_activity(self):
        events = await get_activity_log()
        self.panels[4].update(events)

    def _handle_key(self, key):
        """Handle keyboard input. Returns False to quit."""
        if key == ord("q"):
            return False
        elif key == ord("r"):
            self._last_refresh = {k: 0.0 for k in self._last_refresh}
        elif key in (ord("1"), ord("2"), ord("3"), ord("4"), ord("5")):
            self.focused_panel = key - ord("1")
        elif key == ord("\t"):
            self.focused_panel = (self.focused_panel + 1) % 5
        elif key == ord("?"):
            self.show_help_overlay = not self.show_help_overlay
        elif key == 27:  # Escape
            self.show_help_overlay = False
        elif self.show_help_overlay:
            self.show_help_overlay = False
        return True

    async def _main_loop(self, stdscr):
        """Async main loop with curses."""
        self.stdscr = stdscr
        self.running = True

        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)

        self._init_colors()

        # Fill background
        h, w = stdscr.getmaxyx()
        bg = self._color(self.CP_NORMAL)
        try:
            for row in range(h):
                stdscr.addnstr(row, 0, " " * w, w, bg)
        except curses.error:
            pass

        # Initial data load
        await self._refresh_data(force=True)

        while self.running:
            try:
                key = stdscr.getch()
            except curses.error:
                key = -1

            if key != -1:
                if not self._handle_key(key):
                    break

            await self._refresh_data()

            stdscr.erase()
            self._draw_header()
            self._draw_panels()
            self._draw_footer()

            if self.show_help_overlay:
                self._draw_help_overlay()

            stdscr.refresh()
            await asyncio.sleep(0.1)

    def run(self):
        """Start the curses application."""
        locale.setlocale(locale.LC_ALL, "")

        def _curses_main(stdscr):
            asyncio.run(self._main_loop(stdscr))

        curses.wrapper(_curses_main)


def main():
    """Entry point for console_scripts."""
    app = CICDashboard()
    app.run()


if __name__ == "__main__":
    main()
