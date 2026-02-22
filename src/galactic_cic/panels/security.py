"""Security Status panel for GalacticCIC."""

from textual.widgets import Static
from rich.text import Text

from galactic_cic.data.collectors import get_security_status


class SecurityPanel(Static):
    """Panel showing security status."""

    DEFAULT_CSS = """
    SecurityPanel {
        height: 100%;
        border: solid #1a5c1a;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "SECURITY STATUS"

    async def refresh_data(self) -> None:
        """Refresh security data asynchronously."""
        data = await get_security_status()
        content = self._build_content(data)
        self.update(content)

    def _build_content(self, data: dict) -> Text:
        """Render the panel content."""
        text = Text()

        intrusions = data.get("ssh_intrusions", 0)
        if intrusions == 0:
            text.append("  SSH:      ", style="#0d7a0d")
            text.append("\u2705 No intrusions\n", style="#33ff33")
        elif intrusions < 10:
            text.append("  SSH:      ", style="#0d7a0d")
            text.append(
                f"\u26a0\ufe0f  {intrusions} failed attempts\n", style="#ccaa00"
            )
        else:
            text.append("  SSH:      ", style="#0d7a0d")
            text.append(
                f"\u274c {intrusions} failed attempts\n", style="#cc3333"
            )

        ports = data.get("listening_ports", 0)
        expected = data.get("expected_ports", 4)
        if ports <= expected:
            text.append("  Ports:    ", style="#0d7a0d")
            text.append(
                f"\u2705 {ports} listening (expected)\n", style="#33ff33"
            )
        else:
            text.append("  Ports:    ", style="#0d7a0d")
            text.append(
                f"\u26a0\ufe0f  {ports} listening ({expected} expected)\n",
                style="#ccaa00",
            )

        ufw_active = data.get("ufw_active", False)
        text.append("  UFW:      ", style="#0d7a0d")
        if ufw_active:
            text.append("\u2705 Active\n", style="#33ff33")
        else:
            text.append("\u26a0\ufe0f  Inactive\n", style="#ccaa00")

        f2b_active = data.get("fail2ban_active", False)
        text.append("  Fail2ban: ", style="#0d7a0d")
        if f2b_active:
            text.append("\u2705 Active\n", style="#33ff33")
        else:
            text.append("\u274c Inactive\n", style="#cc3333")

        root_enabled = data.get("root_login_enabled", True)
        text.append("  RootLogin:", style="#0d7a0d")
        if root_enabled:
            text.append(" \u26a0\ufe0f  Enabled\n", style="#ccaa00")
        else:
            text.append(" \u2705 Disabled\n", style="#33ff33")

        return text
