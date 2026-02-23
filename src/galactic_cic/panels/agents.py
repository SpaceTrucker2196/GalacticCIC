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
            st.append(f"  Error loading agents\n", "red")
            st.append(f"  {error[:50]}\n", "red dim")
            return st

        if not agents:
            st.append("  No agents found\n", "dim")
            return st

        for agent in agents:
            name = agent.get("name", "unknown")
            status = agent.get("status", "unknown").upper()
            model = agent.get("model", "")
            style = "green" if status == "ONLINE" else "red"
            st.append(f"  {name:12} ", "green")
            st.append(f"{status}", style)
            if model:
                st.append(f"  ({model})", "dim")
            st.append("\n")

        st.append("\n")

        sessions = status_data.get("sessions", 0)
        model = status_data.get("model", "unknown")
        gateway = status_data.get("gateway_status", "unknown")

        st.append("  Sessions: ", "dim")
        st.append(f"{sessions} active\n", "green")
        st.append("  Model: ", "dim")
        st.append(f"{model}\n", "green")
        st.append("  Gateway: ", "dim")
        gw_style = "green" if gateway == "running" else "yellow"
        st.append(f"{gateway}\n", gw_style)

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
            elif "ONLINE" in line:
                attr = self.c_normal
            elif "Sessions:" in line or "Model:" in line or "Gateway:" in line:
                attr = self.c_normal
            elif "No agents" in line:
                attr = self.c_normal
            self._safe_addstr(win, y + i, x, line, attr, width)
