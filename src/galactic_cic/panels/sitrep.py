"""SITREP panel for curses TUI — channels, updates, action items."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


class SitrepPanel(BasePanel):
    """Panel showing operational SITREP: channels, updates, action items."""

    TITLE = "SITREP"

    def __init__(self):
        super().__init__()
        self.channels = []
        self.update_info = {"available": False, "current": "", "latest": ""}
        self.action_items = []

    def update(self, channels=None, update_info=None, action_items=None):
        """Update panel data."""
        if channels is not None:
            self.channels = channels
        if update_info is not None:
            self.update_info = update_info
        if action_items is not None:
            self.action_items = action_items

    def _build_content(self):
        """Build content as StyledText for testability."""
        st = StyledText()

        # ── Channels ──
        st.append("  Channels\n", "table_heading")
        if self.channels:
            for ch in self.channels:
                name = ch.get("name", "?")
                state = ch.get("state", "?").upper()
                detail = ch.get("detail", "")
                if state == "OK":
                    icon, style = "●", "green"
                elif state == "WARN":
                    icon, style = "▲", "yellow"
                else:
                    icon, style = "✖", "red"
                st.append(f"  {icon} {name:<12}", style)
                st.append(f" {state:<6}", style)
                if detail:
                    st.append(f" {detail}", "green")
                st.append("\n")
        else:
            st.append("  No channels configured\n", "green")

        st.append("\n")

        # ── Update ──
        st.append("  Update Status\n", "table_heading")
        if self.update_info.get("available"):
            st.append("  ▲ UPDATE AVAILABLE\n", "yellow")
            cur = self.update_info.get("current", "?")
            lat = self.update_info.get("latest", "?")
            st.append(f"  Current: {cur}\n", "green")
            st.append(f"  Latest:  {lat}\n", "yellow")
            st.append("  Run: openclaw update\n", "green")
        else:
            st.append("  ● Up to date\n", "green")

        st.append("\n")

        # ── Action Items ──
        st.append("  Action Items\n", "table_heading")
        if self.action_items:
            for item in self.action_items:
                sev = item.get("severity", "info")
                text = item.get("text", "?")
                if sev in ("error", "critical"):
                    st.append(f"  ✖ {text}\n", "red")
                elif sev == "warn":
                    st.append(f"  ▲ {text}\n", "yellow")
                else:
                    st.append(f"  ● {text}\n", "green")
        else:
            st.append("  ● ALL CLEAR\n", "green")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render SITREP content into curses window."""
        row = 0

        # ── Channels ──
        self._safe_addstr(win, y + row, x, "  Channels", self.c_table_heading, width)
        row += 1

        if self.channels:
            for ch in self.channels:
                if row >= height:
                    break
                name = ch.get("name", "?")
                state = ch.get("state", "?").upper()
                detail = ch.get("detail", "")
                if state == "OK":
                    icon, attr = "●", self.c_normal
                elif state == "WARN":
                    icon, attr = "▲", self.c_warn
                else:
                    icon, attr = "✖", self.c_error

                line = f"  {icon} {name:<12} {state:<6}"
                if detail:
                    # Truncate detail to fit
                    max_detail = width - len(line) - 1
                    if max_detail > 0:
                        line += f" {detail[:max_detail]}"
                self._safe_addstr(win, y + row, x, line, attr, width)
                row += 1
        else:
            if row < height:
                self._safe_addstr(win, y + row, x, "  No channels configured",
                                  self.c_dim, width)
                row += 1

        row += 1  # blank line

        # ── Update ──
        if row < height:
            self._safe_addstr(win, y + row, x, "  Update Status",
                              self.c_table_heading, width)
            row += 1

        if row < height:
            if self.update_info.get("available"):
                self._safe_addstr(win, y + row, x, "  ▲ UPDATE AVAILABLE",
                                  self.c_warn, width)
                row += 1
                if row < height:
                    cur = self.update_info.get("current", "?")
                    self._safe_addstr(win, y + row, x, f"  Current: {cur}",
                                      self.c_normal, width)
                    row += 1
                if row < height:
                    lat = self.update_info.get("latest", "?")
                    self._safe_addstr(win, y + row, x, f"  Latest:  {lat}",
                                      self.c_warn, width)
                    row += 1
                if row < height:
                    self._safe_addstr(win, y + row, x, "  Run: openclaw update",
                                      self.c_dim, width)
                    row += 1
            else:
                self._safe_addstr(win, y + row, x, "  ● Up to date",
                                  self.c_normal, width)
                row += 1

        row += 1  # blank line

        # ── Action Items ──
        if row < height:
            self._safe_addstr(win, y + row, x, "  Action Items",
                              self.c_table_heading, width)
            row += 1

        if self.action_items:
            for item in self.action_items:
                if row >= height:
                    break
                sev = item.get("severity", "info")
                text = item.get("text", "?")
                if sev in ("error", "critical"):
                    icon, attr = "✖", self.c_error
                elif sev == "warn":
                    icon, attr = "▲", self.c_warn
                else:
                    icon, attr = "●", self.c_normal
                self._safe_addstr(win, y + row, x, f"  {icon} {text}",
                                  attr, width)
                row += 1
        else:
            if row < height:
                self._safe_addstr(win, y + row, x, "  ● ALL CLEAR",
                                  self.c_normal, width)
                row += 1

    def _draw_detail(self, win, y, x, height, width):
        """Full-screen detail view for SITREP."""
        row = 0

        self._safe_addstr(win, y + row, x, "  SITREP — Detail View", self.c_highlight, width)
        row += 2

        # Channels
        self._safe_addstr(win, y + row, x, "  Channels", self.c_table_heading, width)
        row += 1
        if self.channels:
            for ch in self.channels:
                if row >= height:
                    break
                name = ch.get("name", "?")
                state = ch.get("state", "?").upper()
                enabled = ch.get("enabled", "?")
                detail = ch.get("detail", "")
                if state == "OK":
                    icon, attr = "●", self.c_normal
                elif state == "WARN":
                    icon, attr = "▲", self.c_warn
                else:
                    icon, attr = "✖", self.c_error
                line = f"    {icon} {name:<14} Enabled: {enabled:<4} State: {state:<6} {detail}"
                self._safe_addstr(win, y + row, x, line[:width], attr, width)
                row += 1
        else:
            self._safe_addstr(win, y + row, x, "    No channels configured", self.c_dim, width)
            row += 1
        row += 1

        # Update
        self._safe_addstr(win, y + row, x, "  Update Status", self.c_table_heading, width)
        row += 1
        if self.update_info.get("available"):
            self._safe_addstr(win, y + row, x, "    ▲ UPDATE AVAILABLE", self.c_warn, width)
            row += 1
            cur = self.update_info.get("current", "?")
            lat = self.update_info.get("latest", "?")
            self._safe_addstr(win, y + row, x, f"    Current version:  {cur}", self.c_normal, width)
            row += 1
            self._safe_addstr(win, y + row, x, f"    Latest version:   {lat}", self.c_warn, width)
            row += 1
            self._safe_addstr(win, y + row, x, "    Command:          openclaw update", self.c_dim, width)
            row += 1
        else:
            self._safe_addstr(win, y + row, x, "    ● Up to date", self.c_normal, width)
            row += 1
        row += 1

        # Action Items
        self._safe_addstr(win, y + row, x, "  Action Items", self.c_table_heading, width)
        row += 1
        if self.action_items:
            for i, item in enumerate(self.action_items, 1):
                if row >= height:
                    break
                sev = item.get("severity", "info")
                text = item.get("text", "?")
                if sev in ("error", "critical"):
                    icon, attr = "✖", self.c_error
                elif sev == "warn":
                    icon, attr = "▲", self.c_warn
                else:
                    icon, attr = "●", self.c_normal
                self._safe_addstr(win, y + row, x,
                    f"    {i}. {icon} [{sev.upper():<8}] {text}", attr, width)
                row += 1
        else:
            self._safe_addstr(win, y + row, x, "    ● ALL CLEAR — No action items", self.c_normal, width)
            row += 1
