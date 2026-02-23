"""Agent Fleet Status panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class AgentFleetPanel(BasePanel):
    """Panel showing agent fleet status."""

    TITLE = "Agent Fleet Status"

    def __init__(self):
        super().__init__()
        self.agents_data = {"agents": [], "error": None}
        self.status_data = {
            "sessions": 0, "model": "unknown", "gateway_status": "unknown",
        }

    def update(self, agents_data, status_data):
        """Update panel data from collectors."""
        self.agents_data = agents_data or self.agents_data
        self.status_data = status_data or self.status_data

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

        for agent in agents:
            name = agent.get("name", "unknown")
            model = agent.get("model", "")
            storage = agent.get("storage", "?")
            tokens = agent.get("tokens", "0k")
            sessions = agent.get("sessions", 0)

            st.append(f"  {name:12}", "green")
            st.append(f" {model:14}", "green")
            st.append(f" {storage:>5}", "green")
            st.append(f" {tokens:>5}tok", "green")
            if sessions > 0:
                st.append(f" {sessions}s", "green")
            st.append("\n")

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
        st = self._build_content(self.agents_data, self.status_data)
        lines = st.plain.split("\n")
        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            if "Error" in line or "OFFLINE" in line:
                attr = self.c_error
            self._safe_addstr(win, y + i, x, line, attr, width)
