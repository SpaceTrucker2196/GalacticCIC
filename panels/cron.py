"""Cron Jobs panel for CIC Dashboard."""

from textual.widgets import Static
from rich.text import Text

from data.collectors import get_cron_jobs


class CronJobsPanel(Static):
    """Panel showing cron job status."""

    DEFAULT_CSS = """
    CronJobsPanel {
        height: 100%;
        border: solid green;
        padding: 0 1;
    }
    """

    STATUS_ICONS = {
        "ok": ("\u2705", "green"),       # checkmark
        "error": ("\u274c", "red"),      # X
        "idle": ("\u23f3", "yellow"),    # hourglass
        "running": ("\U0001f504", "cyan"),  # arrows
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "CRON JOBS"

    async def refresh_data(self) -> None:
        """Refresh cron job data asynchronously."""
        data = await get_cron_jobs()
        content = self._render_content(data)
        self.update(content)

    def _render_content(self, data: dict) -> Text:
        """Render the panel content."""
        text = Text()

        jobs = data.get("jobs", [])
        if not jobs:
            text.append("  No cron jobs found\n", style="dim")
            if data.get("error"):
                text.append(f"  Error: {data['error'][:40]}\n", style="red dim")
            return text

        for job in jobs:
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            last_run = job.get("last_run", "")
            errors = job.get("error_count", 0)

            icon, color = self.STATUS_ICONS.get(status, ("\u2753", "dim"))

            text.append(f"  {icon} ", style=color)
            text.append(f"{name:14}", style="white")

            if last_run:
                text.append(f" {last_run}", style="dim")

            if errors and errors > 0:
                text.append(f" ({errors} err)", style="red")

            text.append("\n")

        return text
