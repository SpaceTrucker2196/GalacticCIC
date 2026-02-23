"""Activity Log panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class ActivityLogPanel(BasePanel):
    """Panel showing activity log."""

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
        self._filter = ""

    def update(self, events):
        """Update panel data from collectors."""
        self.events = events if events is not None else self.events

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

    def _draw_content(self, win, y, x, height, width):
        """Render activity log content into curses window."""
        filtered = self.events
        if self._filter:
            filtered = [
                e for e in self.events
                if self._filter.lower() in e.get("message", "").lower()
                or self._filter.lower() in e.get("type", "").lower()
            ]

        for i, event in enumerate(filtered[:height]):
            st = self._format_event(event)
            line = st.plain
            level = event.get("level", "info")
            attr = self.c_normal
            if level == "error":
                attr = self.c_error
            elif level in ("warn", "warning"):
                attr = self.c_warn
            else:
                attr = self.c_normal
            self._safe_addstr(win, y + i, x, line, attr, width)
