"""Server Health panel for curses TUI."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


# Unicode sparkline block characters (8 levels)
SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


class ServerHealthPanel(BasePanel):
    """Panel showing server health metrics with Tufte sparklines."""

    TITLE = "Server Health"

    def __init__(self):
        super().__init__()
        self.health = {
            "cpu_percent": 0.0, "mem_percent": 0.0,
            "mem_used": "0G", "mem_total": "0G",
            "disk_percent": 0.0, "disk_used": "0G", "disk_total": "0G",
            "load_avg": [0.0, 0.0, 0.0], "uptime": "unknown",
        }
        self.server_trends = {}
        self.network_history = []
        self.network_current = 0
        self.top_ips = []
        self.processes = []
        # Sparkline history arrays
        self.cpu_history = []
        self.mem_history = []
        self.disk_history = []
        # 24h averages for reference lines
        self.cpu_avg = None
        self.mem_avg = None
        self.disk_avg = None
        self.net_avg = None

    def update(self, health, server_trends=None, network_history=None,
               network_current=0, top_ips=None, cpu_history=None,
               mem_history=None, disk_history=None, cpu_avg=None,
               mem_avg=None, disk_avg=None, net_avg=None,
               processes=None):
        """Update panel data from collectors."""
        self.health = health or self.health
        self.server_trends = server_trends or self.server_trends
        if network_history is not None:
            self.network_history = network_history
        self.network_current = network_current
        if top_ips is not None:
            self.top_ips = top_ips
        if cpu_history is not None:
            self.cpu_history = cpu_history
        if mem_history is not None:
            self.mem_history = mem_history
        if disk_history is not None:
            self.disk_history = disk_history
        self.cpu_avg = cpu_avg
        self.mem_avg = mem_avg
        self.disk_avg = disk_avg
        self.net_avg = net_avg
        if processes is not None:
            self.processes = processes

    def _build_process_table(self):
        """Build a Table for top processes."""
        table = Table(
            columns=["PID", "USER", "CPU%", "MEM%", "COMMAND"],
            widths=[7, 9, 6, 6, 20],
            borders=False,
            padding=0,
            header=True,
        )
        for proc in self.processes[:5]:
            cpu_val = float(proc.get("cpu", "0"))
            style = "green"
            if cpu_val >= 50:
                style = "red"
            elif cpu_val >= 25:
                style = "yellow"
            table.add_row([
                proc.get("pid", "?"),
                proc.get("user", "?"),
                proc.get("cpu", "0"),
                proc.get("mem", "0"),
                proc.get("command", "?"),
            ], style=style)
        return table

    def _build_content(self, health, server_trends=None):
        """Build content as StyledText -- used by tests and rendering."""
        st = StyledText()
        if server_trends is None:
            server_trends = {}

        # CPU sparkline
        cpu = health.get("cpu_percent", 0)
        cpu_trend = server_trends.get("cpu_trend", "")
        sparkline = self._make_sparkline(self.cpu_history)
        st.append("  CPU:  ", "green")
        st.append(sparkline, self._bar_color(cpu))
        avg_str = f"  avg:{self.cpu_avg:.0f}%" if self.cpu_avg is not None else ""
        trend_str = f" {cpu_trend}" if cpu_trend else ""
        st.append(f"  {cpu:3.0f}%{trend_str}{avg_str}\n", "green")

        # MEM sparkline
        mem = health.get("mem_percent", 0)
        mem_used = health.get("mem_used", "?")
        mem_total = health.get("mem_total", "?")
        mem_trend = server_trends.get("mem_trend", "")
        sparkline = self._make_sparkline(self.mem_history)
        st.append("  MEM:  ", "green")
        st.append(sparkline, self._bar_color(mem))
        avg_str = f"  avg:{self.mem_avg:.0f}%" if self.mem_avg is not None else ""
        trend_str = f" {mem_trend}" if mem_trend else ""
        st.append(f"  {mem:3.0f}%{trend_str}{avg_str}  {mem_used}/{mem_total}\n", "green")

        # DISK sparkline
        disk = health.get("disk_percent", 0)
        disk_used = health.get("disk_used", "?")
        disk_total = health.get("disk_total", "?")
        disk_trend = server_trends.get("disk_trend", "")
        sparkline = self._make_sparkline(self.disk_history)
        st.append("  DISK: ", "green")
        st.append(sparkline, self._bar_color(disk))
        avg_str = f"  avg:{self.disk_avg:.0f}%" if self.disk_avg is not None else ""
        trend_str = f" {disk_trend}" if disk_trend else ""
        st.append(f"  {disk:3.0f}%{trend_str}{avg_str}  {disk_used}/{disk_total}\n", "green")

        # NET sparkline
        sparkline = self._make_sparkline(self.network_history)
        st.append("  NET:  ", "green")
        st.append(sparkline, "green")
        avg_str = f"  avg:{self.net_avg:.0f}" if self.net_avg is not None else ""
        st.append(f"  {self.network_current:3d}{avg_str}\n", "green")

        st.append("\n")

        # LOAD + UP on same line
        load = health.get("load_avg", [0, 0, 0])
        uptime = health.get("uptime", "unknown")
        st.append(f"  LOAD: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}", "green")
        st.append(f"   UP: {uptime}\n", "green")

        # Top Processes
        if self.processes:
            st.append("\n")
            st.append("  Top Processes:\n", "table_heading")
            proc_table = self._build_process_table()
            proc_st = proc_table.render()
            # Preserve per-row styling
            offset = len(st._text)
            st._text += proc_st._text
            for span in proc_st._spans:
                st._spans.append(StyledText.Span(
                    span.start + offset, span.end + offset, span.style
                ))

        # Top IPs
        if self.top_ips:
            st.append("\n")
            st.append("  Top IPs:\n", "table_heading")
            table = Table(
                columns=["IP", "#", "Host"],
                widths=[18, 4, 18],
                borders=False,
                padding=0,
                header=False,
            )
            for entry in self.top_ips:
                table.add_row([
                    entry.get("ip", "?"),
                    str(entry.get("count", 0)),
                    entry.get("hostname", "unknown"),
                ])
            table_st = table.render()
            for line in table_st.plain.split("\n"):
                if line.strip():
                    st.append(f"    {line}\n", "green")

        return st

    @staticmethod
    def _make_sparkline(values, width=16):
        """Create a Tufte sparkline from a list of numeric values."""
        if not values:
            return SPARK_CHARS[0] * width

        # Take the last `width` values
        recent = values[-width:]
        max_val = max(recent) if recent else 1
        if max_val == 0:
            return SPARK_CHARS[0] * len(recent)

        sparkline = ""
        for v in recent:
            idx = int((v / max_val) * (len(SPARK_CHARS) - 1))
            idx = min(idx, len(SPARK_CHARS) - 1)
            sparkline += SPARK_CHARS[idx]

        return sparkline

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
        row = 0

        # Sparklines section
        for label, history, pct, trend_key, avg_val, extra in [
            ("CPU:  ", self.cpu_history, self.health.get("cpu_percent", 0),
             "cpu_trend", self.cpu_avg, ""),
            ("MEM:  ", self.mem_history, self.health.get("mem_percent", 0),
             "mem_trend", self.mem_avg,
             f"  {self.health.get('mem_used', '?')}/{self.health.get('mem_total', '?')}"),
            ("DISK: ", self.disk_history, self.health.get("disk_percent", 0),
             "disk_trend", self.disk_avg,
             f"  {self.health.get('disk_used', '?')}/{self.health.get('disk_total', '?')}"),
        ]:
            if row >= height:
                break
            sparkline = self._make_sparkline(history)
            trend = self.server_trends.get(trend_key, "")
            avg_str = f"  avg:{avg_val:.0f}%" if avg_val is not None else ""
            trend_str = f" {trend}" if trend else ""
            line = f"  {label}{sparkline}  {pct:3.0f}%{trend_str}{avg_str}{extra}"

            attr = self.c_normal
            if pct >= 90:
                attr = self.c_error
            elif pct >= 70:
                attr = self.c_warn
            self._safe_addstr(win, y + row, x, line, attr, width)
            row += 1

        # NET sparkline
        if row < height:
            sparkline = self._make_sparkline(self.network_history)
            avg_str = f"  avg:{self.net_avg:.0f}" if self.net_avg is not None else ""
            line = f"  NET:  {sparkline}  {self.network_current:3d}{avg_str}"
            self._safe_addstr(win, y + row, x, line, self.c_normal, width)
            row += 1

        row += 1  # blank line

        # LOAD + UP
        if row < height:
            load = self.health.get("load_avg", [0, 0, 0])
            uptime = self.health.get("uptime", "unknown")
            line = f"  LOAD: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}   UP: {uptime}"
            self._safe_addstr(win, y + row, x, line, self.c_normal, width)
            row += 1

        # Top Processes
        if self.processes and row + 2 < height:
            row += 1  # blank line
            self._safe_addstr(
                win, y + row, x, "  Top Processes:",
                self.c_table_heading, width,
            )
            row += 1
            proc_table = self._build_process_table()
            rows_drawn = proc_table.draw(
                win, y + row, x, width,
                self.c_normal, self.c_error, self.c_warn,
            )
            row += rows_drawn

        # Top IPs
        if self.top_ips and row + 1 < height:
            row += 1  # blank line
            self._safe_addstr(
                win, y + row, x, "  Top IPs:",
                self.c_table_heading, width,
            )
            row += 1
            for entry in self.top_ips:
                if row >= height:
                    break
                ip = entry.get("ip", "?")
                count = str(entry.get("count", 0))
                host = entry.get("hostname", "unknown")
                line = f"    {ip:<18}{count:>3} {host}"
                self._safe_addstr(win, y + row, x, line, self.c_normal, width)
                row += 1
