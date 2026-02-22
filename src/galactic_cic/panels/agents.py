"""Agent Fleet Status panel for GalacticCIC."""

from textual.app import ComposeResult
from textual.widgets import Static
from rich.text import Text

from galactic_cic.data.collectors import get_agents_data, get_openclaw_status


class AgentFleetPanel(Static):
    """Panel showing agent fleet status."""

    DEFAULT_CSS = """
    AgentFleetPanel {
        height: 100%;
        border: solid green;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "AGENT FLEET STATUS"

    def compose(self) -> ComposeResult:
        yield Static("Loading...", id="agents-content")

    async def refresh_data(self) -> None:
        """Refresh agent data asynchronously."""
        agents_data = await get_agents_data()
        status_data = await get_openclaw_status()
        content = self._build_content(agents_data, status_data)
        content_widget = self.query_one("#agents-content", Static)
        content_widget.update(content)

    def _build_content(self, agents_data: dict, status_data: dict) -> Text:
        """Render the panel content."""
        text = Text()

        agents = agents_data.get("agents", [])
        error = agents_data.get("error")

        if error and not agents:
            text.append("  Error loading agents\n", style="red")
            text.append(f"  {error[:50]}\n", style="red dim")
        elif not agents:
            text.append("  No agents found\n", style="dim")
        else:
            for agent in agents:
                name = agent.get("name", "unknown")
                status = agent.get("status", "unknown")
                model = agent.get("model", "")

                if status.lower() == "online":
                    status_style = "green"
                else:
                    status_style = "red"

                text.append(f"  {name:12} ", style="cyan")
                text.append("\u25cf ", style=status_style)
                text.append(f"{status.upper()}", style=status_style)
                if model:
                    text.append(f"  ({model})", style="dim")
                text.append("\n")

        text.append("\n")

        sessions = status_data.get("sessions", 0)
        model = status_data.get("model", "unknown")
        gateway = status_data.get("gateway_status", "unknown")

        text.append("  Sessions: ", style="dim")
        text.append(f"{sessions} active\n", style="cyan")

        text.append("  Model: ", style="dim")
        text.append(f"{model}\n", style="cyan")

        text.append("  Gateway: ", style="dim")
        if gateway == "running":
            text.append(f"{gateway}\n", style="green")
        else:
            text.append(f"{gateway}\n", style="yellow")

        return text
