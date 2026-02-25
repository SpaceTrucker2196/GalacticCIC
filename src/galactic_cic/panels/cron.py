"""Cron Jobs panel for curses TUI."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


class CronJobsPanel(BasePanel):
    """Panel showing cron job status."""

    TITLE = "Cron Jobs"

    STATUS_ICONS = {
        "ok": "\u2713",
        "error": "\u2717",
        "idle": "\u25cc",
        "running": "\u21bb",
    }

    def __init__(self):
        super().__init__()
        self.cron_data = {"jobs": [], "error": None}

    def update(self, cron_data):
        """Update panel data from collectors."""
        self.cron_data = cron_data or self.cron_data

    def _build_table(self, data):
        """Build a Table from cron data."""
        table = Table(
            columns=["", "Job", "Last", "Next"],
            widths=[2, 18, 9, 9],
            borders=False,
            padding=0,
            header=True,
        )
        for job in data.get("jobs", []):
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            error_count = job.get("error_count", 0)

            # Show error count inline with job name
            if status == "error" and error_count and error_count > 0:
                suffix = f"({error_count}err)"
                max_len = 17 - len(suffix) - 1
                name = name[:max_len] + " " + suffix
            else:
                name = name[:17]

            last_run = job.get("last_run", "--")[:8]
            next_run = job.get("next_run", "--")[:8]
            icon = self.STATUS_ICONS.get(status, "?")
            style = "red" if status == "error" else "green"
            table.add_row([icon, name, last_run, next_run], style=style)
        return table

    def _build_content(self, data):
        """Build content as StyledText -- used by tests and rendering."""
        st = StyledText()

        jobs = data.get("jobs", [])
        if not jobs:
            st.append("  No cron jobs found\n", "green")
            if data.get("error"):
                st.append(f"  Error: {data['error'][:40]}\n", "red")
            return st

        table = self._build_table(data)
        table_st = table.render()

        # Preserve per-row styling from the table (don't flatten to .plain)
        offset = len(st._text)
        st._text += table_st._text
        for span in table_st._spans:
            st._spans.append(StyledText.Span(
                span.start + offset, span.end + offset, span.style
            ))

        # Summary line
        error_jobs = [j for j in jobs if j.get("status") == "error"]
        total_errors = sum(j.get("error_count", 0) for j in error_jobs)
        if total_errors > 0:
            st.append(
                f"\n  {len(error_jobs)} job(s) with {total_errors} error(s)\n",
                "red",
            )

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render cron jobs content into curses window."""
        jobs = self.cron_data.get("jobs", [])

        if not jobs:
            self._safe_addstr(win, y, x, "  No cron jobs found", self.c_normal, width)
            if self.cron_data.get("error"):
                err_msg = f"  Error: {self.cron_data['error'][:width - 10]}"
                self._safe_addstr(win, y + 1, x, err_msg, self.c_error, width)
            return

        table = self._build_table(self.cron_data)
        rows_drawn = table.draw(win, y, x, width, self.c_normal, self.c_error, self.c_warn)

        # Summary below table
        error_jobs = [j for j in jobs if j.get("status") == "error"]
        total_errors = sum(j.get("error_count", 0) for j in error_jobs)
        summary_y = y + rows_drawn
        if total_errors > 0 and summary_y < y + height:
            msg = f"  {len(error_jobs)} job(s) with {total_errors} error(s)"
            self._safe_addstr(win, summary_y, x, msg, self.c_error, width)
