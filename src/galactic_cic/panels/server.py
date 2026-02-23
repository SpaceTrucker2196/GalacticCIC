"""Server Health panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class ServerHealthPanel(BasePanel):
    """Panel showing server health metrics."""

    TITLE = "Server Health"

    def __init__(self):
        super().__init__()
        self.health = {
            "cpu_percent": 0.0, "mem_percent": 0.0,
            "mem_used": "0G", "mem_total": "0G",
            "disk_percent": 0.0, "disk_used": "0G", "disk_total": "0G",
            "load_avg": [0.0, 0.0, 0.0], "uptime": "unknown",
        }

    def update(self, health):
        """Update panel data from collectors."""
        self.health = health or self.health

    def _build_content(self, health):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        cpu = health.get("cpu_percent", 0)
        st.append("  CPU:  ", "dim")
        st.append(self._make_bar(cpu), self._bar_color(cpu))
        st.append(f"  {cpu:4.0f}%\n")

        mem = health.get("mem_percent", 0)
        mem_used = health.get("mem_used", "?")
        mem_total = health.get("mem_total", "?")
        st.append("  MEM:  ", "dim")
        st.append(self._make_bar(mem), self._bar_color(mem))
        st.append(f"  {mem:4.0f}%  {mem_used}/{mem_total}\n")

        disk = health.get("disk_percent", 0)
        disk_used = health.get("disk_used", "?")
        disk_total = health.get("disk_total", "?")
        st.append("  DISK: ", "dim")
        st.append(self._make_bar(disk), self._bar_color(disk))
        st.append(f"  {disk:4.0f}%  {disk_used}/{disk_total}\n")

        st.append("\n")

        load = health.get("load_avg", [0, 0, 0])
        st.append("  LOAD: ", "dim")
        st.append(f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}\n", "green")

        uptime = health.get("uptime", "unknown")
        st.append("  UP:   ", "dim")
        st.append(f"{uptime}\n", "green")

        return st

    @staticmethod
    def _make_bar(percent, width=10):
        """Create a progress bar string."""
        filled = int(percent / 100 * width)
        empty = width - filled
        return "\u2588" * filled + "\u2591" * empty

    @staticmethod
    def _bar_color(percent):
        """Return color name based on usage percentage."""
        if percent >= 90:
            return "red"
        elif percent >= 70:
            return "yellow"
        else:
            return "green"

    def _draw_content(self, win, y, x, height, width):
        """Render server health content into curses window."""
        st = self._build_content(self.health)
        lines = st.plain.split("\n")
        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            # Color bars based on percentage thresholds
            if "CPU:" in line or "MEM:" in line or "DISK:" in line:
                # Label in dim, but we draw the whole line in normal
                # and rely on the bar characters being visible
                attr = self.c_normal
                # Check for threshold coloring
                if "\u2588" in line:
                    # Find the percentage in the line
                    try:
                        pct_str = line.split("%")[0].split()[-1]
                        pct = float(pct_str)
                        if pct >= 90:
                            attr = self.c_error
                        elif pct >= 70:
                            attr = self.c_warn
                        else:
                            attr = self.c_normal
                    except (ValueError, IndexError):
                        attr = self.c_normal
            elif "LOAD:" in line or "UP:" in line:
                attr = self.c_normal
            self._safe_addstr(win, y + i, x, line, attr, width)
