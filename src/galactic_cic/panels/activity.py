"""Activity Log panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class ActivityLogPanel(BasePanel):
    """Panel showing activity log with ERRORS (upper) and RECENT (lower) sections."""

    TITLE = "Activity Log"

    TYPE_ICONS = {
        "ssh": "\U0001f511",
        "cron": "\u23f0",
        "openclaw": "\U0001f980",
        "system": "\U0001f4bb",
    }

    def __init__(self):
        super().__init__()
        self.events = []
        self.errors = []
        self._filter = ""

    def update(self, events, errors=None):
        """Update panel data from collectors."""
        self.events = events if events is not None else self.events
        if errors is not None:
            self.errors = errors

    def set_filter(self, filter_text):
        """Set filter for activity log."""
        self._filter = filter_text

    @staticmethod
    def _format_event(event):
        """Format a single event for display — used by tests."""
        st = StyledText()

        time_str = event.get("time", "??:??")
        message = event.get("message", "")
        level = event.get("level", "info")
        event_type = event.get("type", "")

        st.append(f"  {time_str:>8} ", "dim")

        if level == "error":
            style = "red"
        elif level in ("warn", "warning"):
            style = "yellow"
        else:
            style = "white"

        type_icons = {
            "ssh": "\U0001f511",
            "cron": "\u23f0",
            "openclaw": "\U0001f980",
            "system": "\U0001f4bb",
        }
        icon = type_icons.get(event_type, "\u2022")
        st.append(f"{icon} ", "green")

        if len(message) > 60:
            message = message[:57] + "..."
        st.append(message, style)

        return st

    @staticmethod
    def _format_line(event):
        """Format event as HH:MM [source] message — for split layout."""
        time_str = event.get("time", "??:??")
        # Normalize to HH:MM
        if len(time_str) > 5:
            time_str = time_str[-5:] if ":" in time_str[-5:] else time_str[:5]
        src = event.get("type", "sys")[:6]
        msg = event.get("message", "")
        if len(msg) > 55:
            msg = msg[:52] + "..."
        return f"  {time_str:>5} [{src}] {msg}"

    def _draw_content(self, win, y, x, height, width):
        """Render activity log with ERRORS (upper, red) and RECENT (lower, green)."""
        if height < 3:
            return

        filtered = self.events
        if self._filter:
            filtered = [
                e for e in self.events
                if self._filter.lower() in e.get("message", "").lower()
                or self._filter.lower() in e.get("type", "").lower()
            ]

        # ERRORS section (upper)
        row = 0
        self._safe_addstr(win, y + row, x, " ERRORS:", self.c_error, width)
        row += 1

        if self.errors:
            for err in self.errors[:max(2, height // 3)]:
                if row >= height - 2:
                    break
                line = self._format_line(err)
                self._safe_addstr(win, y + row, x, line, self.c_error, width)
                row += 1
        else:
            self._safe_addstr(win, y + row, x, "  (none)", self.c_normal, width)
            row += 1

        # Separator
        if row < height:
            sep = " " + "\u2500" * (width - 2)
            self._safe_addstr(win, y + row, x, sep, self.c_normal, width)
            row += 1

        # RECENT section (lower, green)
        if row < height:
            self._safe_addstr(win, y + row, x, " RECENT:", self.c_normal, width)
            row += 1

        for event in filtered[:(height - row)]:
            if row >= height:
                break
            line = self._format_line(event)
            level = event.get("level", "info")
            attr = self.c_normal
            if level == "error":
                attr = self.c_error
            elif level in ("warn", "warning"):
                attr = self.c_warn
            self._safe_addstr(win, y + row, x, line, attr, width)
            row += 1
