"""Activity Log panel for CIC Dashboard."""

from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from rich.text import Text

from data.collectors import get_activity_log


class ActivityLogPanel(Static):
    """Panel showing activity log."""

    DEFAULT_CSS = """
    ActivityLogPanel {
        height: 100%;
        border: solid green;
        padding: 0 1;
    }

    ActivityLogPanel RichLog {
        height: 100%;
        scrollbar-size: 1 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "ACTIVITY LOG"
        self._filter = ""

    def compose(self) -> ComposeResult:
        yield RichLog(id="activity-log", wrap=True, markup=True)

    async def refresh_data(self) -> None:
        """Refresh activity log asynchronously."""
        events = await get_activity_log()
        log_widget = self.query_one("#activity-log", RichLog)
        log_widget.clear()

        for event in events:
            if self._filter and self._filter.lower() not in event.get("message", "").lower():
                continue

            line = self._format_event(event)
            log_widget.write(line)

    def _format_event(self, event: dict) -> Text:
        """Format a single event for display."""
        text = Text()

        time_str = event.get("time", "??:??")
        message = event.get("message", "")
        level = event.get("level", "info")
        event_type = event.get("type", "")

        # Time
        text.append(f"  {time_str:>8} ", style="dim")

        # Color based on level
        if level == "error":
            style = "red"
        elif level == "warn" or level == "warning":
            style = "yellow"
        else:
            style = "white"

        # Type icon
        type_icons = {
            "ssh": "\U0001f511",      # key
            "cron": "\u23f0",         # alarm clock
            "openclaw": "\U0001f980", # crab
            "system": "\U0001f4bb",   # computer
        }
        icon = type_icons.get(event_type, "\u2022")
        text.append(f"{icon} ", style="cyan")

        # Message (truncate if too long)
        if len(message) > 60:
            message = message[:57] + "..."
        text.append(message, style=style)

        return text

    def set_filter(self, filter_text: str) -> None:
        """Set filter for activity log."""
        self._filter = filter_text
