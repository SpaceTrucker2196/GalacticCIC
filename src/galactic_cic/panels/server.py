"""Server Health panel for GalacticCIC."""

from textual.widgets import Static
from rich.text import Text

from galactic_cic.data.collectors import get_server_health


class ServerHealthPanel(Static):
    """Panel showing server health metrics."""

    DEFAULT_CSS = """
    ServerHealthPanel {
        height: 100%;
        border: solid #1a5c1a;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "SERVER HEALTH"

    async def refresh_data(self) -> None:
        """Refresh server health data asynchronously."""
        health = await get_server_health()
        content = self._build_content(health)
        self.update(content)

    def _build_content(self, health: dict) -> Text:
        """Render the panel content with progress bars."""
        text = Text()

        cpu = health.get("cpu_percent", 0)
        text.append("  CPU:  ", style="#0d7a0d")
        text.append(self._make_bar(cpu), style=self._bar_color(cpu))
        text.append(f"  {cpu:4.0f}%\n")

        mem = health.get("mem_percent", 0)
        mem_used = health.get("mem_used", "?")
        mem_total = health.get("mem_total", "?")
        text.append("  MEM:  ", style="#0d7a0d")
        text.append(self._make_bar(mem), style=self._bar_color(mem))
        text.append(f"  {mem:4.0f}%  {mem_used}/{mem_total}\n")

        disk = health.get("disk_percent", 0)
        disk_used = health.get("disk_used", "?")
        disk_total = health.get("disk_total", "?")
        text.append("  DISK: ", style="#0d7a0d")
        text.append(self._make_bar(disk), style=self._bar_color(disk))
        text.append(f"  {disk:4.0f}%  {disk_used}/{disk_total}\n")

        text.append("\n")

        load = health.get("load_avg", [0, 0, 0])
        text.append("  LOAD: ", style="#0d7a0d")
        text.append(f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}\n", style="#33ff33")

        uptime = health.get("uptime", "unknown")
        text.append("  UP:   ", style="#0d7a0d")
        text.append(f"{uptime}\n", style="#33ff33")

        return text

    def _make_bar(self, percent: float, width: int = 10) -> str:
        """Create a progress bar string."""
        filled = int(percent / 100 * width)
        empty = width - filled
        return "\u2588" * filled + "\u2591" * empty

    @staticmethod
    def _bar_color(percent: float) -> str:
        """Return color based on usage percentage."""
        if percent >= 90:
            return "red"
        elif percent >= 70:
            return "yellow"
        else:
            return "green"
