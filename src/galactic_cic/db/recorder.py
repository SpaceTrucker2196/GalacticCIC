"""Record metrics from collectors into the SQLite database."""

import time


class MetricsRecorder:
    """Records collector data into the metrics database."""

    def __init__(self, db):
        self.db = db

    def record_agents(self, agents_data):
        """Record agent metrics from collector data."""
        if not agents_data:
            return
        ts = time.time()
        agents = agents_data.get("agents", [])
        for agent in agents:
            name = agent.get("name", "unknown")
            tokens = agent.get("tokens_numeric", 0)
            sessions = agent.get("sessions", 0)
            storage = agent.get("storage_bytes", 0)
            model = agent.get("model", "")
            self.db.execute(
                "INSERT INTO agent_metrics "
                "(timestamp, agent_name, tokens_used, sessions, storage_bytes, model) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, name, tokens, sessions, storage, model),
            )
        self.db.commit()

    def record_server(self, health):
        """Record server health metrics."""
        if not health:
            return
        ts = time.time()
        cpu = health.get("cpu_percent", 0.0)
        mem_used_mb = health.get("mem_used_mb", 0.0)
        mem_total_mb = health.get("mem_total_mb", 0.0)
        disk_used_gb = health.get("disk_used_gb", 0.0)
        disk_total_gb = health.get("disk_total_gb", 0.0)
        load = health.get("load_avg", [0.0, 0.0, 0.0])
        self.db.execute(
            "INSERT INTO server_metrics "
            "(timestamp, cpu_percent, mem_used_mb, mem_total_mb, "
            "disk_used_gb, disk_total_gb, load_1m, load_5m, load_15m) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, cpu, mem_used_mb, mem_total_mb, disk_used_gb, disk_total_gb,
             load[0] if len(load) > 0 else 0.0,
             load[1] if len(load) > 1 else 0.0,
             load[2] if len(load) > 2 else 0.0),
        )
        self.db.commit()

    def record_cron(self, cron_data):
        """Record cron job metrics."""
        if not cron_data:
            return
        ts = time.time()
        jobs = cron_data.get("jobs", [])
        for job in jobs:
            name = job.get("name", "unknown")
            status = job.get("status", "idle")
            last_run = job.get("last_run", "")
            next_run = job.get("next_run", "")
            self.db.execute(
                "INSERT INTO cron_metrics "
                "(timestamp, job_name, status, last_run, next_run) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, name, status, last_run, next_run),
            )
        self.db.commit()

    def record_network(self, network_data):
        """Record network activity metrics."""
        if not network_data:
            return
        ts = time.time()
        self.db.execute(
            "INSERT INTO network_metrics "
            "(timestamp, active_connections, unique_ips) "
            "VALUES (?, ?, ?)",
            (ts,
             network_data.get("active_connections", 0),
             network_data.get("unique_ips", 0)),
        )
        self.db.commit()

    def record_security(self, security_data):
        """Record security metrics."""
        if not security_data:
            return
        ts = time.time()
        self.db.execute(
            "INSERT INTO security_metrics "
            "(timestamp, ssh_intrusions, ports_open, ufw_active, "
            "fail2ban_active, root_login_enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts,
             security_data.get("ssh_intrusions", 0),
             security_data.get("listening_ports", 0),
             1 if security_data.get("ufw_active", False) else 0,
             1 if security_data.get("fail2ban_active", False) else 0,
             1 if security_data.get("root_login_enabled", True) else 0),
        )
        # Record port scan details
        ports = security_data.get("ports_detail", [])
        for port_info in ports:
            port_num = port_info.get("port", 0)
            try:
                port_num = int(port_num)
            except (ValueError, TypeError):
                port_num = 0
            self.db.execute(
                "INSERT INTO port_scans "
                "(timestamp, port, service, state) "
                "VALUES (?, ?, ?, ?)",
                (ts, port_num,
                 port_info.get("service", ""),
                 port_info.get("state", "open")),
            )
        self.db.commit()
