"""Cron Jobs panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class CronJobsPanel(BasePanel):
    """Panel showing cron job status."""

    TITLE = "Cron Jobs"

    STATUS_ICONS = {
        "ok": ("✅", "green"),
        "error": ("❌", "red"),
        "idle": ("⏳", "green"),
        "running": ("🔄", "green"),
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
            st.append("  No cron jobs found\n", "green")
            if data.get("error"):
                st.append(f"  Error: {data['error'][:40]}\n", "red")
            return st

        for job in jobs:
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            last_run = job.get("last_run", "")
            next_run = job.get("next_run", "")
            errors = job.get("error_count", 0)

            icon, color = self.STATUS_ICONS.get(status, ("❓", "green"))

            # Status-based color
            if status == "error":
                line_color = "red"
            else:
                line_color = "green"

            st.append(f"  {icon} ", line_color)
            st.append(f"{name:20}", line_color)

            # Last run
            if last_run:
                st.append(f" ran:{last_run:>6}", "green")
            else:
                st.append(f" ran:{'--':>6}", "green")

            # Next run
            if next_run:
                st.append(f" next:{next_run:>6}", "green")

            if errors and errors > 0:
                st.append(f" ({errors}err)", "red")

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
            if "❌" in line or "err)" in line:
                attr = self.c_error
            elif "⚠" in line:
                attr = self.c_warn
            self._safe_addstr(win, y + i, x, line, attr, width)
