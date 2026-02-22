"""Security Status panel for CIC Dashboard."""

from textual.widgets import Static
from rich.text import Text

from data.collectors import get_security_status


class SecurityPanel(Static):
    """Panel showing security status."""

    DEFAULT_CSS = """
    SecurityPanel {
        height: 100%;
        border: solid green;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "SECURITY STATUS"

    async def refresh_data(self) -> None:
        """Refresh security data asynchronously."""
        data = await get_security_status()
        content = self._render_content(data)
        self.update(content)

    def _render_content(self, data: dict) -> Text:
        """Render the panel content."""
        text = Text()

        # SSH intrusions
        intrusions = data.get("ssh_intrusions", 0)
        if intrusions == 0:
            text.append("  SSH:      ", style="dim")
            text.append("\u2705 No intrusions\n", style="green")
        elif intrusions < 10:
            text.append("  SSH:      ", style="dim")
            text.append(f"\u26a0\ufe0f  {intrusions} failed attempts\n", style="yellow")
        else:
            text.append("  SSH:      ", style="dim")
            text.append(f"\u274c {intrusions} failed attempts\n", style="red")

        # Listening ports
        ports = data.get("listening_ports", 0)
        expected = data.get("expected_ports", 4)
        if ports <= expected:
            text.append("  Ports:    ", style="dim")
            text.append(f"\u2705 {ports} listening (expected)\n", style="green")
        else:
            text.append("  Ports:    ", style="dim")
            text.append(f"\u26a0\ufe0f  {ports} listening ({expected} expected)\n", style="yellow")

        # UFW
        ufw_active = data.get("ufw_active", False)
        text.append("  UFW:      ", style="dim")
        if ufw_active:
            text.append("\u2705 Active\n", style="green")
        else:
            text.append("\u26a0\ufe0f  Inactive\n", style="yellow")

        # Fail2ban
        f2b_active = data.get("fail2ban_active", False)
        text.append("  Fail2ban: ", style="dim")
        if f2b_active:
            text.append("\u2705 Active\n", style="green")
        else:
            text.append("\u274c Inactive\n", style="red")

        # Root login
        root_enabled = data.get("root_login_enabled", True)
        text.append("  RootLogin:", style="dim")
        if root_enabled:
            text.append(" \u26a0\ufe0f  Enabled\n", style="yellow")
        else:
            text.append(" \u2705 Disabled\n", style="green")

        return text
