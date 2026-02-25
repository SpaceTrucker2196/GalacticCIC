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

    def _draw_detail(self, win, y, x, height, width):
        """Full-screen detail view for Cron Jobs."""
        row = 0
        jobs = self.cron_data.get("jobs", [])

        self._safe_addstr(win, y + row, x, "  CRON JOBS — Detail View", self.c_highlight, width)
        row += 2

        if not jobs:
            self._safe_addstr(win, y + row, x, "  No cron jobs configured", self.c_normal, width)
            return

        # Wider table with all columns
        from galactic_cic.panels.base import Table
        table = Table(
            columns=["St", "Job Name", "Schedule", "Last Run", "Next Run", "Agent", "Errs"],
            widths=[3, min(25, width // 4), min(25, width // 4), 12, 12, 12, 5],
            borders=False, padding=1, header=True,
        )
        for job in jobs:
            status = job.get("status", "idle")
            icon = self.STATUS_ICONS.get(status, "?")
            name = job.get("name", "?")
            schedule = job.get("schedule", "?")
            last = job.get("last_run", "--")
            next_r = job.get("next_run", "--")
            agent = job.get("agent", "?")
            errs = str(job.get("error_count", 0))
            style = "red" if status == "error" else "green"
            table.add_row([icon, name, schedule, last, next_r, agent, errs], style=style)

        rows_drawn = table.draw(win, y + row, x + 2, width - 4,
                               self.c_normal, self.c_error, self.c_warn)
        row += rows_drawn + 1

        # Summary
        error_jobs = [j for j in jobs if j.get("status") == "error"]
        ok_jobs = [j for j in jobs if j.get("status") == "ok"]
        idle_jobs = [j for j in jobs if j.get("status") == "idle"]
        if row < height:
            summary = f"  Total: {len(jobs)}  ✓ OK: {len(ok_jobs)}  ✖ Error: {len(error_jobs)}  ○ Idle: {len(idle_jobs)}"
            self._safe_addstr(win, y + row, x, summary,
                             self.c_error if error_jobs else self.c_normal, width)
            row += 2

        # Error details
        if error_jobs and row + 2 < height:
            self._safe_addstr(win, y + row, x, "  Error Details", self.c_table_heading, width)
            row += 1
            for job in error_jobs:
                if row + 3 >= height:
                    break
                name = job.get("name", "?")
                errs = job.get("error_count", 0)
                last = job.get("last_run", "?")
                self._safe_addstr(win, y + row, x,
                    f"    ✖ {name}: {errs} consecutive errors, last: {last}", self.c_error, width)
                row += 1
