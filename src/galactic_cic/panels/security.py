"""Security Status panel for curses TUI."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


class SecurityPanel(BasePanel):
    """Panel showing security status."""

    TITLE = "Security Status"
    TITLE_NMAP = "Security Status [NMAP]"

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
        self.attacker_scans = {}  # ip -> {open_ports, os_guess}
        self.geo_data = {}  # ip -> {country_code, city, isp}
        self.nmap_scanning = False

    def draw(self, win, y, x, height, width, color_normal, color_highlight,
             color_warn, color_error, color_dim):
        """Override to show [NMAP] indicator in title when scanning."""
        # Swap title when nmap is active
        if self.nmap_scanning:
            self.TITLE = self.TITLE_NMAP
        else:
            self.TITLE = "Security Status"
        super().draw(win, y, x, height, width, color_normal, color_highlight,
                     color_warn, color_error, color_dim)

        # If nmap scanning, redraw just the [NMAP] part of the title in yellow
        if self.nmap_scanning:
            import curses
            title_str = f" {self.TITLE} "
            nmap_pos = title_str.find("[NMAP]")
            if nmap_pos >= 0:
                try:
                    win.addstr(y, x + 2 + nmap_pos, "[NMAP]", color_warn)
                except curses.error:
                    pass

    def update(self, data, ssh_summary=None, last_nmap_time=None,
               attacker_scans=None, geo_data=None, nmap_scanning=None):
        """Update panel data from collectors."""
        self.security_data = data or self.security_data
        if ssh_summary is not None:
            self.ssh_summary = ssh_summary
        if last_nmap_time is not None:
            self.last_nmap_time = last_nmap_time
        if attacker_scans is not None:
            self.attacker_scans = attacker_scans
        if geo_data is not None:
            self.geo_data = geo_data
        if nmap_scanning is not None:
            self.nmap_scanning = nmap_scanning

    def _get_cc(self, ip):
        """Get 2-letter country code for an IP."""
        geo = self.geo_data.get(ip, {})
        return geo.get("country_code", "?") if geo else "?"

    def _build_content(self, data):
        """Build content as StyledText — used by tests and rendering."""
        st = StyledText()

        intrusions = data.get("ssh_intrusions", 0)
        if intrusions == 0:
            st.append("  SSH:  No intrusions\n", "green")
        elif intrusions < 10:
            st.append(f"  SSH:  {intrusions} failed attempts\n", "yellow")
        else:
            st.append(f"  SSH:  {intrusions} failed attempts\n", "red")

        # Port details as table
        ports_detail = data.get("ports_detail", [])
        port_count = len(ports_detail) if ports_detail else data.get("listening_ports", 0)
        st.append(f"  Ports: {port_count} open\n", "green")

        if ports_detail:
            table = Table(
                columns=["Port", "Service"],
                widths=[7, 20],
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

        st.append("\n")

        # SSH Login Summary with country codes
        accepted = self.ssh_summary.get("accepted", [])
        failed = self.ssh_summary.get("failed", [])

        if accepted:
            st.append("  SSH Logins (24h):\n", "table_heading")
            for entry in accepted:
                ip = entry.get("ip", "?")
                count = str(entry.get("count", 0))
                host = entry.get("hostname", "unknown")[:13]
                cc = self._get_cc(ip)
                st.append(f"   {ip:<18}{count:>3} {host:<14}{cc}\n", "green")

        st.append("  SSH Failed (24h):\n", "table_heading")
        if failed:
            for entry in failed:
                ip = entry.get("ip", "?")
                count = str(entry.get("count", 0))
                host = entry.get("hostname", "unknown")[:13]
                cc = self._get_cc(ip)
                st.append(f"   {ip:<18}{count:>3} {host:<14}{cc}\n", "red")
                # Show nmap scan results if available
                scan = self.attacker_scans.get(ip, {})
                ports = scan.get("open_ports", "")
                os_guess = scan.get("os_guess", "")
                if ports or os_guess:
                    parts = []
                    if ports:
                        parts.append(f"ports: {ports}")
                    if os_guess:
                        parts.append(f"os: {os_guess}")
                    st.append(f"     {('  '.join(parts))}\n", "red")
        else:
            st.append("   (none)\n", "green")

        st.append("\n")

        # UFW + Fail2ban on same line
        ufw_status = "Active" if data.get("ufw_active", False) else "Inactive"
        f2b_status = "Active" if data.get("fail2ban_active", False) else "Inactive"
        ufw_style = "green" if data.get("ufw_active") else "yellow"
        f2b_style = "green" if data.get("fail2ban_active") else "red"
        st.append(f"  UFW: {ufw_status}", ufw_style)
        st.append(f"  Fail2ban: {f2b_status}\n", f2b_style)

        # Root login
        root_enabled = data.get("root_login_enabled", True)
        if root_enabled:
            st.append("  RootLogin: Enabled", "yellow")
        else:
            st.append("  RootLogin: Disabled", "green")

        st.append("\n")

        # Attacker Scan Summary
        if self.attacker_scans:
            st.append("  Attacker Scans:\n", "table_heading")
            if self.last_nmap_time:
                st.append(f"  Last scan: {self.last_nmap_time}\n", "green")
            for ip, scan in self.attacker_scans.items():
                ports = scan.get("open_ports", "none")
                os_guess = scan.get("os_guess", "")
                cc = self._get_cc(ip)
                st.append(f"   {ip:<18}", "red")
                st.append(f" [{cc}]", "yellow")
                if ports and ports != "none":
                    st.append(f"  ports: {ports}", "red")
                if os_guess:
                    st.append(f"  os: {os_guess}", "red")
                st.append("\n")
        elif self.last_nmap_time:
            st.append(f"  Last nmap: {self.last_nmap_time}  No attackers scanned\n", "green")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render security status content into curses window."""
        st = self._build_content(self.security_data)
        lines = st.plain.split("\n")

        # Build a set of failed IPs for quick lookup
        failed_ips = set()
        for e in self.ssh_summary.get("failed", []):
            ip = e.get("ip", "")
            if ip:
                failed_ips.add(ip)

        for i, line in enumerate(lines[:height]):
            if not line:
                continue
            attr = self.c_normal
            if "SSH Logins" in line or "SSH Failed" in line or "Attacker Scans" in line:
                attr = self.c_table_heading
            elif "Last scan:" in line or "Last nmap:" in line:
                attr = self.c_normal
            elif "failed attempts" in line:
                intrusions = self.security_data.get("ssh_intrusions", 0)
                attr = self.c_error if intrusions >= 10 else self.c_warn
            elif "Inactive" in line:
                if "Fail2ban" in line:
                    attr = self.c_error
                elif "UFW" in line:
                    attr = self.c_warn
            elif "Enabled" in line:
                attr = self.c_warn
            elif "ports:" in line or "os:" in line:
                attr = self.c_error
            elif any(ip in line for ip in failed_ips):
                attr = self.c_error
            self._safe_addstr(win, y + i, x, line, attr, width)

    def _draw_detail(self, win, y, x, height, width):
        """Full-screen detail view for Security."""
        row = 0
        data = self.security_data

        self._safe_addstr(win, y + row, x, "  SECURITY STATUS — Detail View", self.c_highlight, width)
        row += 2

        # SSH Summary
        self._safe_addstr(win, y + row, x, "  SSH Access", self.c_table_heading, width)
        row += 1
        intrusions = data.get("ssh_intrusions", 0)
        attr = self.c_error if intrusions >= 10 else (self.c_warn if intrusions > 0 else self.c_normal)
        self._safe_addstr(win, y + row, x, f"    Failed attempts (24h): {intrusions}", attr, width)
        row += 2

        # Accepted logins
        accepted = self.ssh_summary.get("accepted", [])
        if accepted:
            self._safe_addstr(win, y + row, x, "  Accepted Logins (24h)", self.c_table_heading, width)
            row += 1
            for entry in accepted:
                if row >= height:
                    break
                ip = entry.get("ip", "?")
                count = entry.get("count", 0)
                host = entry.get("hostname", "?")
                cc = self._get_cc(ip)
                self._safe_addstr(win, y + row, x,
                    f"    {ip:<18} {count:>4}x  {host:<20} [{cc}]", self.c_normal, width)
                row += 1
            row += 1

        # Failed logins
        failed = self.ssh_summary.get("failed", [])
        if failed:
            self._safe_addstr(win, y + row, x, "  Failed Logins (24h)", self.c_table_heading, width)
            row += 1
            for entry in failed:
                if row + 3 >= height:
                    break
                ip = entry.get("ip", "?")
                count = entry.get("count", 0)
                host = entry.get("hostname", "?")
                cc = self._get_cc(ip)
                self._safe_addstr(win, y + row, x,
                    f"    {ip:<18} {count:>4}x  {host:<20} [{cc}]", self.c_error, width)
                row += 1
                # Show nmap scan if available
                scan = self.attacker_scans.get(ip, {})
                geo = self.geo_data.get(ip, {})
                if scan.get("open_ports") or scan.get("os_guess") or geo.get("city"):
                    parts = []
                    if geo.get("city"):
                        parts.append(f"loc: {geo['city']}")
                    if geo.get("isp"):
                        parts.append(f"isp: {geo['isp']}")
                    if scan.get("open_ports"):
                        parts.append(f"ports: {scan['open_ports']}")
                    if scan.get("os_guess"):
                        parts.append(f"os: {scan['os_guess']}")
                    self._safe_addstr(win, y + row, x,
                        f"      {' · '.join(parts)}", self.c_warn, width)
                    row += 1
            row += 1

        # Firewall & Services
        if row + 4 < height:
            self._safe_addstr(win, y + row, x, "  Firewall & Services", self.c_table_heading, width)
            row += 1
            ufw = "Active" if data.get("ufw_active") else "Inactive"
            f2b = "Active" if data.get("fail2ban_active") else "Inactive"
            root = "Enabled" if data.get("root_login_enabled") else "Disabled"
            self._safe_addstr(win, y + row, x, f"    UFW:            {ufw}",
                             self.c_normal if data.get("ufw_active") else self.c_warn, width)
            row += 1
            self._safe_addstr(win, y + row, x, f"    Fail2ban:       {f2b}",
                             self.c_normal if data.get("fail2ban_active") else self.c_error, width)
            row += 1
            self._safe_addstr(win, y + row, x, f"    Root login:     {root}",
                             self.c_normal if not data.get("root_login_enabled") else self.c_warn, width)
            row += 2

        # Open Ports
        ports = data.get("ports_detail", [])
        if ports and row + 2 < height:
            self._safe_addstr(win, y + row, x, f"  Open Ports ({len(ports)})", self.c_table_heading, width)
            row += 1
            for p in ports:
                if row >= height:
                    break
                port = p.get("port", "?")
                svc = p.get("service", "?")
                self._safe_addstr(win, y + row, x, f"    {port:<8} {svc}", self.c_normal, width)
                row += 1
            row += 1

        # Attacker Scans
        if self.attacker_scans and row + 2 < height:
            self._safe_addstr(win, y + row, x,
                f"  Attacker Scans ({len(self.attacker_scans)})", self.c_table_heading, width)
            row += 1
            if self.last_nmap_time:
                self._safe_addstr(win, y + row, x,
                    f"    Last scan: {self.last_nmap_time}", self.c_dim, width)
                row += 1
            for ip, scan in self.attacker_scans.items():
                if row >= height:
                    break
                ports_s = scan.get("open_ports", "none")
                os_s = scan.get("os_guess", "")
                cc = self._get_cc(ip)
                geo = self.geo_data.get(ip, {})
                city = geo.get("city", "")
                line = f"    {ip:<18} [{cc}]"
                if city:
                    line += f" {city}"
                if ports_s and ports_s != "none":
                    line += f"  ports: {ports_s}"
                if os_s:
                    line += f"  os: {os_s}"
                self._safe_addstr(win, y + row, x, line, self.c_error, width)
                row += 1
