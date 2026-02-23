"""Security Status panel for curses TUI."""

from galactic_cic.panels.base import BasePanel, StyledText, Table


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
        self.ssh_summary = {"accepted": [], "failed": []}
        self.last_nmap_time = ""

    def update(self, data, ssh_summary=None, last_nmap_time=None):
        """Update panel data from collectors."""
        self.security_data = data or self.security_data
        if ssh_summary is not None:
            self.ssh_summary = ssh_summary
        if last_nmap_time is not None:
            self.last_nmap_time = last_nmap_time

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

        # Port details as table
        ports_detail = data.get("ports_detail", [])
        port_count = len(ports_detail) if ports_detail else data.get("listening_ports", 0)
        st.append(f"  Ports:    {port_count} open\n", "green")

        if ports_detail:
            table = Table(
                columns=["Port", "Service"],
                widths=[7, 16],
                borders=False,
                padding=0,
                header=False,
            )
            for port_info in ports_detail:
                port = str(port_info.get("port", "?"))
                service = port_info.get("service", "unknown")
                table.add_row([port, service])
            table_st = table.render()
            for line in table_st.plain.split("\n"):
                if line.strip():
                    st.append(f"    {line}\n", "green")

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

        # Last nmap scan time
        if self.last_nmap_time:
            st.append(f"  Scan:     {self.last_nmap_time}\n", "dim")

        # SSH Login Summary
        accepted = self.ssh_summary.get("accepted", [])
        failed = self.ssh_summary.get("failed", [])

        if accepted:
            st.append("\n")
            st.append("  SSH Logins (24h):\n", "dim")
            table = Table(
                columns=["IP", "#", "Host", "Last"],
                widths=[18, 4, 16, 14],
                borders=False,
                padding=0,
                header=False,
            )
            for entry in accepted:
                table.add_row([
                    entry.get("ip", "?"),
                    str(entry.get("count", 0)),
                    entry.get("hostname", "unknown"),
                    entry.get("last_seen", ""),
                ])
            table_st = table.render()
            for line in table_st.plain.split("\n"):
                if line.strip():
                    st.append(f"    {line}\n", "green")

        if failed:
            st.append("  SSH Failed (24h):\n", "dim")
            table = Table(
                columns=["IP", "#", "Host", "Last"],
                widths=[18, 4, 16, 14],
                borders=False,
                padding=0,
                header=False,
            )
            for entry in failed:
                table.add_row([
                    entry.get("ip", "?"),
                    str(entry.get("count", 0)),
                    entry.get("hostname", "unknown"),
                    entry.get("last_seen", ""),
                ], style="red")
            table_st = table.render()
            for line in table_st.plain.split("\n"):
                if line.strip():
                    st.append(f"    {line}\n", "red")

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
            elif "SSH Failed" in line or (self.ssh_summary.get("failed") and
                    any(e.get("ip", "") in line for e in self.ssh_summary["failed"])):
                attr = self.c_error
            self._safe_addstr(win, y + i, x, line, attr, width)
