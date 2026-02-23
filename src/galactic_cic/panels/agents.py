"""Agent Fleet Status panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


def _format_tokens(n):
    """Format token count: 126000 -> '126k', 1500000 -> '1500k'."""
    if n >= 1000:
        return f"{n // 1000}k"
    return str(n)


class AgentFleetPanel(BasePanel):
    """Panel showing agent fleet status."""

    TITLE = "Agent Fleet Status"

    def __init__(self):
        super().__init__()
        self.agents_data = {"agents": [], "error": None}
        self.status_data = {
            "sessions": 0, "model": "unknown", "gateway_status": "unknown",
        }
        self.tokens_per_hour = {}

    def update(self, agents_data, status_data, tokens_per_hour=None):
        """Update panel data from collectors."""
        self.agents_data = agents_data or self.agents_data
        self.status_data = status_data or self.status_data
        self.tokens_per_hour = tokens_per_hour or self.tokens_per_hour

    def _build_content(self, agents_data, status_data, tokens_per_hour=None):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()
        agents = agents_data.get("agents", [])
        error = agents_data.get("error")
        if tokens_per_hour is None:
            tokens_per_hour = {}

        if error and not agents:
            st.append("  Error loading agents\n", "red")
            st.append(f"  {error[:50]}\n", "red")
            return st

        if not agents:
            st.append("  No agents found\n", "green")
            return st

        # Header line
        st.append("  AGENT        MODEL          STOR  TOKENS TOK/H  S\n", "green")

        total_tokens = 0
        total_tph = 0
        total_sessions = 0

        for agent in agents:
            name = agent.get("name", "unknown")
            model = agent.get("model", "")
            storage = agent.get("storage", "?")
            tokens = agent.get("tokens", "0k")
            tokens_num = agent.get("tokens_numeric", 0)
            sessions = agent.get("sessions", 0)
            is_default = agent.get("is_default", False)

            total_tokens += tokens_num
            total_sessions += sessions

            # Main agent marker
            display_name = f"{name}*" if is_default else name
            tph = tokens_per_hour.get(name, 0)
            total_tph += tph
            tph_str = f"{_format_tokens(tph)}/h" if tph > 0 else "--"

            st.append(f"  {display_name:12}", "green")
            st.append(f" {model:14}", "green")
            st.append(f" {storage:>5}", "green")
            st.append(f" {tokens:>5}", "green")
            st.append(f" {tph_str:>6}", "green")
            st.append(f"  {sessions}", "green")
            st.append("\n")

        st.append("\n")

        # Total line
        total_tok_str = _format_tokens(total_tokens)
        total_tph_str = _format_tokens(total_tph)
        st.append(
            f"  Total: {total_tok_str} tokens  {total_tph_str}/h"
            f"  {total_sessions} sessions\n",
            "green",
        )

        gateway = status_data.get("gateway_status", "unknown")
        version = status_data.get("version", "")
        gw_style = "green" if gateway == "running" else "red"
        gw_line = f"  Gateway: {gateway}"
        if version:
            gw_line += f"  v{version}"
        st.append(gw_line + "\n", gw_style)

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render agent fleet content into curses window."""
        st = self._build_content(
            self.agents_data, self.status_data, self.tokens_per_hour
        )
        lines = st.plain.split("\n")
        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            if "Error" in line or "OFFLINE" in line:
                attr = self.c_error
            self._safe_addstr(win, y + i, x, line, attr, width)
