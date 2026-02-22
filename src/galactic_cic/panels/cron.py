"""Cron Jobs panel for GalacticCIC."""

from textual.widgets import Static
from rich.text import Text

from galactic_cic.data.collectors import get_cron_jobs


class CronJobsPanel(Static):
    """Panel showing cron job status."""

    DEFAULT_CSS = """
    CronJobsPanel {
        height: 100%;
        overflow: auto;
        background: #020a02;
        border: solid #1a5c1a;
        color: #33ff33;
        padding: 0 1;
    }
    """

    STATUS_ICONS = {
        "ok": ("\u2705", "green"),
        "error": ("\u274c", "red"),
        "idle": ("\u23f3", "yellow"),
        "running": ("\U0001f504", "cyan"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "CRON JOBS"

    async def refresh_data(self) -> None:
        """Refresh cron job data asynchronously."""
        data = await get_cron_jobs()
        content = self._build_content(data)
        self.update(content)

    def _build_content(self, data: dict) -> Text:
        """Render the panel content."""
        text = Text()

        jobs = data.get("jobs", [])
        if not jobs:
            text.append("  No cron jobs found\n", style="#0d7a0d")
            if data.get("error"):
                text.append(
                    f"  Error: {data['error'][:40]}\n", style="red dim"
                )
            return text

        for job in jobs:
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            last_run = job.get("last_run", "")
            errors = job.get("error_count", 0)

            icon, color = self.STATUS_ICONS.get(status, ("\u2753", "dim"))

            text.append(f"  {icon} ", style=color)
            text.append(f"{name:14}", style="#33ff33")

            if last_run:
                text.append(f" {last_run}", style="#0d7a0d")

            if errors and errors > 0:
                text.append(f" ({errors} err)", style="#cc3333")

            text.append("\n")

        return text
