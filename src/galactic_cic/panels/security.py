"""Security Status panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText


class SecurityPanel(BasePanel):
    """Panel showing security status."""

    TITLE = "Security Status"

    def __init__(self):
        super().__init__()
        self.security_data = {
            "ssh_intrusions": 0, "listening_ports": 0,
            "expected_ports": 4, "ufw_active": False,
            "fail2ban_active": False, "root_login_enabled": True,
        }

    def update(self, data):
        """Update panel data from collectors."""
        self.security_data = data or self.security_data

    def _build_content(self, data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        intrusions = data.get("ssh_intrusions", 0)
        if intrusions == 0:
            st.append("  SSH:      ", "dim")
            st.append("No intrusions\n", "green")
        elif intrusions < 10:
            st.append("  SSH:      ", "dim")
            st.append(f"{intrusions} failed attempts\n", "yellow")
        else:
            st.append("  SSH:      ", "dim")
            st.append(f"{intrusions} failed attempts\n", "red")

        ports = data.get("listening_ports", 0)
        expected = data.get("expected_ports", 4)
        if ports <= expected:
            st.append("  Ports:    ", "dim")
            st.append(f"{ports} listening (expected)\n", "green")
        else:
            st.append("  Ports:    ", "dim")
            st.append(f"{ports} listening ({expected} expected)\n", "yellow")

        ufw_active = data.get("ufw_active", False)
        st.append("  UFW:      ", "dim")
        if ufw_active:
            st.append("Active\n", "green")
        else:
            st.append("Inactive\n", "yellow")

        f2b_active = data.get("fail2ban_active", False)
        st.append("  Fail2ban: ", "dim")
        if f2b_active:
            st.append("Active\n", "green")
        else:
            st.append("Inactive\n", "red")

        root_enabled = data.get("root_login_enabled", True)
        st.append("  RootLogin:", "dim")
        if root_enabled:
            st.append(" Enabled\n", "yellow")
        else:
            st.append(" Disabled\n", "green")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render security status content into curses window."""
        st = self._build_content(self.security_data)
        lines = st.plain.split("\n")
        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            if "failed attempts" in line:
                intrusions = self.security_data.get("ssh_intrusions", 0)
                if intrusions >= 10:
                    attr = self.c_error
                else:
                    attr = self.c_warn
            elif "No intrusions" in line or "Active" in line or "Disabled" in line:
                attr = self.c_highlight
            elif "Inactive" in line or "Enabled" in line:
                if "Fail2ban" in line:
                    attr = self.c_error
                else:
                    attr = self.c_warn
            self._safe_addstr(win, y + i, x, line, attr, width)
