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
            "ports_detail": [],
        }

    def update(self, data):
        """Update panel data from collectors."""
        self.security_data = data or self.security_data

    def _build_content(self, data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        intrusions = data.get("ssh_intrusions", 0)
        if intrusions == 0:
            st.append("  SSH:      No intrusions\n", "green")
        elif intrusions < 10:
            st.append(f"  SSH:      {intrusions} failed attempts\n", "yellow")
        else:
            st.append(f"  SSH:      {intrusions} failed attempts\n", "red")

        # Port details
        ports_detail = data.get("ports_detail", [])
        port_count = len(ports_detail) if ports_detail else data.get("listening_ports", 0)
        st.append(f"  Ports:    {port_count} open\n", "green")
        for port_info in ports_detail:
            port = port_info.get("port", "?")
            service = port_info.get("service", "unknown")
            st.append(f"    {port:>5} {service}\n", "green")

        ufw_active = data.get("ufw_active", False)
        if ufw_active:
            st.append("  UFW:      Active\n", "green")
        else:
            st.append("  UFW:      Inactive\n", "yellow")

        f2b_active = data.get("fail2ban_active", False)
        if f2b_active:
            st.append("  Fail2ban: Active\n", "green")
        else:
            st.append("  Fail2ban: Inactive\n", "red")

        root_enabled = data.get("root_login_enabled", True)
        if root_enabled:
            st.append("  RootLogin: Enabled\n", "yellow")
        else:
            st.append("  RootLogin: Disabled\n", "green")

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
                attr = self.c_error if intrusions >= 10 else self.c_warn
            elif "Inactive" in line:
                attr = self.c_error if "Fail2ban" in line else self.c_warn
            elif "Enabled" in line:
                attr = self.c_warn
            self._safe_addstr(win, y + i, x, line, attr, width)
