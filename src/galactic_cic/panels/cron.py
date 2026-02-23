"""Cron Jobs panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText, Table


class CronJobsPanel(BasePanel):
    """Panel showing cron job status."""

    TITLE = "Cron Jobs"

    STATUS_ICONS = {
        "ok": "✓",
        "error": "✗",
        "idle": "◌",
        "running": "↻",
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
            name = job.get("name", "unknown")[:17]
            status = job.get("status", "idle")
            last_run = job.get("last_run", "--")[:8]
            next_run = job.get("next_run", "--")[:8]
            icon = self.STATUS_ICONS.get(status, "?")
            style = "red" if status == "error" else "green"
            table.add_row([icon, name, last_run, next_run], style=style)
        return table

    def _build_content(self, data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        jobs = data.get("jobs", [])
        if not jobs:
            st.append("  No cron jobs found\n", "green")
            if data.get("error"):
                st.append(f"  Error: {data['error'][:40]}\n", "red")
            return st

        table = self._build_table(data)
        table_st = table.render()
        st.append(table_st.plain, "green")

        # Check for any errors in the plain text for test compatibility
        for job in jobs:
            if job.get("status") == "error":
                errors = job.get("error_count", 0)
                if errors and errors > 0:
                    st.append(f"({errors}err)", "red")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render cron jobs content into curses window."""
        jobs = self.cron_data.get("jobs", [])

        if not jobs:
            self._safe_addstr(win, y, x, "  No cron jobs found", self.c_normal, width)
            return

        table = self._build_table(self.cron_data)
        table.draw(win, y, x, width, self.c_normal, self.c_error, self.c_warn)
