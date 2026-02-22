"""GalacticCIC - Combat Information Center TUI for OpenClaw operations monitoring."""

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, Static
from textual.screen import ModalScreen
from rich.text import Text

from galactic_cic.panels import (
    AgentFleetPanel,
    ServerHealthPanel,
    CronJobsPanel,
    SecurityPanel,
    ActivityLogPanel,
)


class HelpScreen(ModalScreen):
    """Help overlay screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: 50;
        height: auto;
        max-height: 80%;
        border: thick #1a5c1a;
        background: #020a02;
        padding: 1 2;
    }

    HelpScreen Static {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._help_text())

    @staticmethod
    def _help_text() -> Text:
        text = Text()
        text.append("CIC Dashboard Help\n", style="bold #4aff4a")
        text.append("=" * 30 + "\n\n", style="#0d7a0d")

        bindings = [
            ("q", "Quit application"),
            ("r", "Force refresh all panels"),
            ("1", "Focus Agent Fleet panel"),
            ("2", "Focus Server Health panel"),
            ("3", "Focus Cron Jobs panel"),
            ("4", "Focus Security panel"),
            ("5", "Focus Activity Log panel"),
            ("Tab", "Cycle focus between panels"),
            ("/", "Filter activity log"),
            ("?", "Show this help"),
            ("Esc", "Close dialogs/clear filter"),
        ]

        for key, desc in bindings:
            text.append(f"  {key:8}", style="#33ff33")
            text.append(f" {desc}\n", style="#1a8c1a")

        text.append("\n")
        text.append("Refresh Rates:\n", style="bold #4aff4a")
        text.append("  Server health:  5s\n", style="#0d7a0d")
        text.append("  Agents/Cron:   30s\n", style="#0d7a0d")
        text.append("  Security:      60s\n", style="#0d7a0d")
        text.append("  Activity log:  10s\n", style="#0d7a0d")

        return text


class CICHeader(Static):
    """Custom header with dual timezone clock."""

    DEFAULT_CSS = """
    CICHeader {
        dock: top;
        height: 1;
        background: #0d1a00;
        color: #33ff33;
        text-style: bold;
    }
    """

    def __init__(self):
        super().__init__()
        self._ct_tz = ZoneInfo("America/Chicago")

    def on_mount(self) -> None:
        self.set_interval(1, self._update_time)
        self._update_time()

    def _update_time(self) -> None:
        now_utc = datetime.now(timezone.utc)
        now_ct = now_utc.astimezone(self._ct_tz)

        text = Text()
        text.append(
            "  \U0001f6f8 CIC \u2014 Combat Information Center",
            style="bold #4aff4a",
        )
        text.append("    ")
        text.append(
            f"[{now_utc.strftime('%H:%M')} UTC / {now_ct.strftime('%H:%M')} CT]",
            style="#33ff33",
        )

        self.update(text)


class CICDashboard(App):
    """Main CIC Dashboard application."""

    CSS = """
    Screen {
        background: #020a02;
    }

    #main-grid {
        layout: grid;
        grid-size: 2 3;
        grid-rows: 1fr 1fr 1fr;
        height: 100%;
        padding: 0;
    }

    #top-left { row-span: 1; column-span: 1; }
    #top-right { row-span: 1; column-span: 1; }
    #mid-left { row-span: 1; column-span: 1; }
    #mid-right { row-span: 1; column-span: 1; }
    #bottom { row-span: 1; column-span: 2; }

    .panel-focused {
        border: double #4aff4a;
    }

    Footer {
        background: #0d1a00;
        color: #33ff33;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("1", "focus_panel('agents')", "Agents", show=False),
        Binding("2", "focus_panel('server')", "Server", show=False),
        Binding("3", "focus_panel('cron')", "Cron", show=False),
        Binding("4", "focus_panel('security')", "Security", show=False),
        Binding("5", "focus_panel('activity')", "Activity", show=False),
        Binding("tab", "cycle_focus", "Next Panel"),
        Binding("slash", "filter_log", "Filter"),
        Binding("question_mark", "show_help", "Help"),
        Binding("escape", "clear_filter", "Clear", show=False),
    ]

    def __init__(self):
        super().__init__()
        self._panel_order = ["agents", "server", "cron", "security", "activity"]
        self._current_panel_index = 0

    def compose(self) -> ComposeResult:
        yield CICHeader()
        with Container(id="main-grid"):
            yield AgentFleetPanel(id="agents")
            yield ServerHealthPanel(id="server")
            yield CronJobsPanel(id="cron")
            yield SecurityPanel(id="security")
            yield ActivityLogPanel(id="activity")
        yield Footer()

    async def on_mount(self) -> None:
        """Set up refresh timers when app mounts."""
        await self.action_refresh_all()
        self.set_interval(5, self._refresh_server)
        self.set_interval(30, self._refresh_agents_cron)
        self.set_interval(60, self._refresh_security)
        self.set_interval(10, self._refresh_activity)

    async def _refresh_server(self) -> None:
        try:
            panel = self.query_one("#server", ServerHealthPanel)
            await panel.refresh_data()
        except Exception:
            pass

    async def _refresh_agents_cron(self) -> None:
        try:
            agents = self.query_one("#agents", AgentFleetPanel)
            cron = self.query_one("#cron", CronJobsPanel)
            await asyncio.gather(
                agents.refresh_data(), cron.refresh_data(),
                return_exceptions=True,
            )
        except Exception:
            pass

    async def _refresh_security(self) -> None:
        try:
            panel = self.query_one("#security", SecurityPanel)
            await panel.refresh_data()
        except Exception:
            pass

    async def _refresh_activity(self) -> None:
        try:
            panel = self.query_one("#activity", ActivityLogPanel)
            await panel.refresh_data()
        except Exception:
            pass

    async def action_refresh_all(self) -> None:
        """Force refresh all panels."""
        await asyncio.gather(
            self._refresh_server(),
            self._refresh_agents_cron(),
            self._refresh_security(),
            self._refresh_activity(),
            return_exceptions=True,
        )

    def action_focus_panel(self, panel_id: str) -> None:
        """Focus a specific panel by ID."""
        try:
            panel = self.query_one(f"#{panel_id}")
            panel.focus()
            for p in self._panel_order:
                self.query_one(f"#{p}").remove_class("panel-focused")
            panel.add_class("panel-focused")
            self._current_panel_index = self._panel_order.index(panel_id)
        except Exception:
            pass

    def action_cycle_focus(self) -> None:
        """Cycle focus to next panel."""
        self._current_panel_index = (
            (self._current_panel_index + 1) % len(self._panel_order)
        )
        panel_id = self._panel_order[self._current_panel_index]
        self.action_focus_panel(panel_id)

    def action_filter_log(self) -> None:
        self.notify("Filter: Press Escape to clear", timeout=2)

    def action_clear_filter(self) -> None:
        try:
            panel = self.query_one("#activity", ActivityLogPanel)
            panel.set_filter("")
            self.call_later(panel.refresh_data)
        except Exception:
            pass

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())


def main():
    """Entry point."""
    app = CICDashboard()
    app.run()


if __name__ == "__main__":
    main()
