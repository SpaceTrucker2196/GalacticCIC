"""Cron Jobs panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class CronJobsPanel(BasePanel):
    """Panel showing cron job status."""

    TITLE = "Cron Jobs"

    STATUS_ICONS = {
        "ok": ("\u2705", "green"),
        "error": ("\u274c", "red"),
        "idle": ("\u23f3", "yellow"),
        "running": ("\U0001f504", "cyan"),
    }

    def __init__(self):
        super().__init__()
        self.cron_data = {"jobs": [], "error": None}

    def update(self, cron_data):
        """Update panel data from collectors."""
        self.cron_data = cron_data or self.cron_data

    def _build_content(self, data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        jobs = data.get("jobs", [])
        if not jobs:
            st.append("  No cron jobs found\n", "dim")
            if data.get("error"):
                st.append(f"  Error: {data['error'][:40]}\n", "red")
            return st

        for job in jobs:
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            last_run = job.get("last_run", "")
            errors = job.get("error_count", 0)

            icon, color = self.STATUS_ICONS.get(status, ("\u2753", "dim"))

            st.append(f"  {icon} ", color)
            st.append(f"{name:14}", "green")

            if last_run:
                st.append(f" {last_run}", "dim")

            if errors and errors > 0:
                st.append(f" ({errors} err)", "red")

            st.append("\n")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render cron jobs content into curses window."""
        st = self._build_content(self.cron_data)
        lines = st.plain.split("\n")
        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            if "\u274c" in line or "err)" in line:
                attr = self.c_error
            elif "\u2705" in line:
                attr = self.c_highlight
            elif "\u23f3" in line:
                attr = self.c_warn
            elif "No cron" in line:
                attr = self.c_dim
            self._safe_addstr(win, y + i, x, line, attr, width)
