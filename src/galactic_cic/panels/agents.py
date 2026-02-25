"""Agent Fleet Status panel for curses TUI."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


class AgentFleetPanel(BasePanel):
    """Panel showing agent fleet status."""

    TITLE = "Agent Fleet"

    def __init__(self):
        super().__init__()
        self.agents_data = {"agents": [], "error": None}
        self.status_data = {
            "sessions": 0, "model": "unknown", "gateway_status": "unknown",
        }

    def update(self, agents_data, status_data, tokens_per_hour=None):
        """Update panel data from collectors."""
        self.agents_data = agents_data or self.agents_data
        self.status_data = status_data or self.status_data
        # Merge tokens_per_hour into agent data for display
        if tokens_per_hour:
            for agent in self.agents_data.get("agents", []):
                name = agent.get("name", "")
                tph = tokens_per_hour.get(name, 0)
                if tph > 0:
                    if tph >= 1000:
                        agent["tokens_per_hour"] = f"{tph // 1000}k"
                    else:
                        agent["tokens_per_hour"] = str(tph)
                else:
                    agent["tokens_per_hour"] = "--"

    def _build_table(self, agents_data):
        """Build a Table from agent data."""
        table = Table(
            columns=["Agent", "Model", "Stor", "Tokens", "Tok/h", "S"],
            widths=[12, 12, 6, 7, 7, 4],
            borders=False,
            padding=0,
        )
        for agent in agents_data.get("agents", []):
            name = agent.get("name", "?")
            if agent.get("is_default"):
                name += "*"
            model = agent.get("model", "")[:11]
            storage = agent.get("storage", "?")
            tokens = agent.get("tokens", "0k")
            tok_h = agent.get("tokens_per_hour", "--")
            sessions = str(agent.get("sessions", 0))
            table.add_row([name, model, storage, tokens, tok_h, sessions])
        return table

    def _build_content(self, agents_data, status_data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()
        agents = agents_data.get("agents", [])
        error = agents_data.get("error")

        if error and not agents:
            st.append("  Error loading agents\n", "red")
            st.append(f"  {error[:50]}\n", "red")
            return st

        if not agents:
            st.append("  No agents found\n", "green")
            return st

        # Use table for agent listing — preserve per-row styling
        table = self._build_table(agents_data)
        table_st = table.render()
        offset = len(st._text)
        st._text += table_st._text
        for span in table_st._spans:
            st._spans.append(StyledText.Span(
                span.start + offset, span.end + offset, span.style
            ))

        st.append("\n")

        total_sessions = status_data.get("sessions", 0)
        gateway = status_data.get("gateway_status", "unknown")
        version = status_data.get("version", "")

        st.append(f"  Sessions: {total_sessions}", "green")
        if version:
            st.append(f"  v{version}", "green")
        st.append("\n")
        gw_style = "green" if gateway == "running" else "red"
        st.append(f"  Gateway: {gateway}\n", gw_style)

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render agent fleet content into curses window."""
        agents = self.agents_data.get("agents", [])
        error = self.agents_data.get("error")

        if error and not agents:
            self._safe_addstr(win, y, x, f"  Error: {error[:width-4]}", self.c_error, width)
            return

        if not agents:
            self._safe_addstr(win, y, x, "  No agents found", self.c_normal, width)
            return

        # Draw agent table
        table = self._build_table(self.agents_data)
        rows_drawn = table.draw(win, y, x, width, self.c_normal, self.c_error, self.c_warn)

        # Summary below table
        summary_y = y + rows_drawn + 1
        if summary_y < y + height:
            total_sessions = self.status_data.get("sessions", 0)
            version = self.status_data.get("version", "")
            gateway = self.status_data.get("gateway_status", "unknown")

            line = f" Sessions: {total_sessions}"
            if version:
                line += f"  v{version}"
            self._safe_addstr(win, summary_y, x, line, self.c_normal, width)

            if summary_y + 1 < y + height:
                gw_attr = self.c_normal if gateway == "running" else self.c_error
                self._safe_addstr(win, summary_y + 1, x, f" Gateway: {gateway}", gw_attr, width)
