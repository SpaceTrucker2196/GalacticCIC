"""Async data collectors for GalacticCIC — shells out to system commands."""

import asyncio
import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any


async def run_command(cmd: str, timeout: float = 10.0) -> tuple[str, str, int]:
    """Run a shell command asynchronously and return (stdout, stderr, returncode)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


async def get_agents_data() -> dict[str, Any]:
    """Get agent fleet status from openclaw agents list with storage and tokens."""
    stdout, stderr, rc = await run_command("openclaw agents list 2>/dev/null")

    agents = []
    if rc == 0 and stdout.strip():
        current_agent = None
        for line in stdout.strip().split("\n"):
            line_stripped = line.strip()
            if line_stripped.startswith("- "):
                # New agent line: "- main (default) (galactic)"
                raw = line_stripped[2:]
                name = raw.split("(")[0].strip()
                is_default = "(default)" in raw
                current_agent = {
                    "name": name,
                    "status": "online",
                    "model": "",
                    "workspace": "",
                    "is_default": is_default,
                }
                agents.append(current_agent)
            elif current_agent and line_stripped.startswith("Model:"):
                model = line_stripped.split(":", 1)[1].strip()
                # Shorten model name
                model = model.replace("anthropic/", "").replace("claude-", "")
                current_agent["model"] = model
            elif current_agent and line_stripped.startswith("Workspace:"):
                current_agent["workspace"] = line_stripped.split(":", 1)[1].strip()

    # Get storage sizes for each agent workspace
    for agent in agents:
        ws = agent.get("workspace", "")
        if ws:
            ws_expanded = ws.replace("~", "/home/spacetrucker")
            size_out, _, size_rc = await run_command(f"du -sh {ws_expanded} 2>/dev/null")
            if size_rc == 0 and size_out.strip():
                agent["storage"] = size_out.strip().split()[0]
                agent["storage_bytes"] = _parse_storage_bytes(agent["storage"])
            else:
                agent["storage"] = "?"
                agent["storage_bytes"] = 0
        else:
            agent["storage"] = "?"
            agent["storage_bytes"] = 0

    # Get token usage per agent from openclaw status
    status_out, _, status_rc = await run_command("openclaw status 2>/dev/null")
    if status_rc == 0 and status_out:
        for agent in agents:
            name = agent["name"]
            # Find sessions for this agent and sum tokens
            total_tokens = 0
            session_count = 0
            for line in status_out.split("\n"):
                if f"agent:{name}:" in line:
                    session_count += 1
                    # Extract token info like "126k/80k (158%)"
                    token_match = re.search(r'(\d+k)/(\d+k)\s*\((\d+)%\)', line)
                    if token_match:
                        used = int(token_match.group(1).replace('k', ''))
                        total_tokens += used
            agent["tokens"] = f"{total_tokens}k" if total_tokens > 0 else "0k"
            agent["tokens_numeric"] = total_tokens * 1000
            agent["sessions"] = session_count

    return {"agents": agents, "error": stderr if rc != 0 else None}


async def get_openclaw_status() -> dict[str, Any]:
    """Get openclaw status including sessions, model, gateway."""
    result: dict[str, Any] = {
        "sessions": 0,
        "model": "unknown",
        "gateway_status": "unknown",
        "version": "unknown",
    }

    stdout, stderr, rc = await run_command(
        "openclaw status --json 2>/dev/null || openclaw status 2>/dev/null"
    )
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            result["sessions"] = data.get(
                "sessions", data.get("active_sessions", 0)
            )
            result["model"] = data.get(
                "model", data.get("default_model", "unknown")
            )
        except json.JSONDecodeError:
            for line in stdout.split("\n"):
                if "session" in line.lower():
                    match = re.search(r"(\d+)", line)
                    if match:
                        result["sessions"] = int(match.group(1))
                if "model" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        result["model"] = parts[1].strip()

    stdout, stderr, rc = await run_command("openclaw gateway status 2>/dev/null")
    if rc == 0:
        result["gateway_status"] = (
            "running" if "running" in stdout.lower() else "stopped"
        )

    stdout, stderr, rc = await run_command(
        "openclaw --version 2>/dev/null || openclaw version 2>/dev/null"
    )
    if rc == 0 and stdout.strip():
        result["version"] = stdout.strip().split("\n")[0]

    return result


# Module-level cache for /proc/stat CPU delta measurement
_prev_cpu_stat: list[int] | None = None


async def get_server_health() -> dict[str, Any]:
    """Get server health metrics from system commands."""
    result: dict[str, Any] = {
        "cpu_percent": 0.0,
        "mem_percent": 0.0,
        "mem_used": "0G",
        "mem_total": "0G",
        "mem_used_mb": 0.0,
        "mem_total_mb": 0.0,
        "disk_percent": 0.0,
        "disk_used": "0G",
        "disk_total": "0G",
        "disk_used_gb": 0.0,
        "disk_total_gb": 0.0,
        "load_avg": [0.0, 0.0, 0.0],
        "uptime": "unknown",
    }

    # Memory
    stdout, _, rc = await run_command("free -h")
    if rc == 0:
        for line in stdout.strip().split("\n"):
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 3:
                    result["mem_total"] = parts[1]
                    result["mem_used"] = parts[2]
                    try:
                        total_val = _parse_size(parts[1])
                        used_val = _parse_size(parts[2])
                        result["mem_total_mb"] = total_val * 1024
                        result["mem_used_mb"] = used_val * 1024
                        if total_val > 0:
                            result["mem_percent"] = (used_val / total_val) * 100
                    except (ValueError, IndexError):
                        pass

    # Disk
    stdout, _, rc = await run_command("df -h /")
    if rc == 0:
        lines = stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                result["disk_total"] = parts[1]
                result["disk_used"] = parts[2]
                result["disk_total_gb"] = _parse_size(parts[1])
                result["disk_used_gb"] = _parse_size(parts[2])
                try:
                    result["disk_percent"] = float(parts[4].rstrip("%"))
                except ValueError:
                    pass

    # Load average and uptime
    stdout, _, rc = await run_command("uptime")
    if rc == 0:
        match = re.search(
            r"load average:\s*([\d.]+),?\s*([\d.]+),?\s*([\d.]+)", stdout
        )
        if match:
            result["load_avg"] = [float(match.group(i)) for i in (1, 2, 3)]

        match = re.search(r"up\s+(.+?),\s+\d+\s+user", stdout)
        if match:
            result["uptime"] = match.group(1).strip()
        else:
            match = re.search(r"up\s+(.+?),\s+load", stdout)
            if match:
                result["uptime"] = match.group(1).strip()

    # CPU from /proc/stat — compare against cached previous reading (no sleep)
    global _prev_cpu_stat
    stdout, _, _ = await run_command("head -1 /proc/stat")
    try:
        cpu_now = [int(x) for x in stdout.split()[1:8]]
        if _prev_cpu_stat is not None:
            idle_prev = _prev_cpu_stat[3] + _prev_cpu_stat[4]
            idle_now = cpu_now[3] + cpu_now[4]
            total_prev = sum(_prev_cpu_stat)
            total_now = sum(cpu_now)
            total_diff = total_now - total_prev
            idle_diff = idle_now - idle_prev
            if total_diff > 0:
                result["cpu_percent"] = ((total_diff - idle_diff) / total_diff) * 100
        _prev_cpu_stat = cpu_now
    except (ValueError, IndexError):
        pass

    return result


def _parse_storage_bytes(size_str: str) -> int:
    """Parse size string like '27M' or '3.2G' to bytes."""
    size_str = size_str.strip().upper()
    multipliers = {
        "K": 1024,
        "M": 1024 ** 2,
        "G": 1024 ** 3,
        "T": 1024 ** 4,
    }
    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return int(float(size_str[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(float(size_str))
    except ValueError:
        return 0


def _parse_size(size_str: str) -> float:
    """Parse size string like '3.2G' or '512M' to float in GB."""
    size_str = size_str.strip().upper()
    multipliers = {
        "K": 1 / 1024 / 1024,
        "M": 1 / 1024,
        "G": 1,
        "T": 1024,
        "P": 1024 * 1024,
    }
    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return float(size_str[:-1]) * mult
            except ValueError:
                return 0.0
    try:
        return float(size_str) / (1024**3)
    except ValueError:
        return 0.0


async def get_cron_jobs() -> dict[str, Any]:
    """Get cron job status from openclaw cron list."""
    stdout, stderr, rc = await run_command("openclaw cron list 2>/dev/null")

    jobs = []
    if rc == 0 and stdout.strip():
        lines = stdout.strip().split("\n")

        # Skip Doctor diagnostic output — find the actual header line
        header_idx = None
        for i, line in enumerate(lines):
            if line.startswith("ID") and "Name" in line and "Schedule" in line:
                header_idx = i
                break

        if header_idx is None or header_idx + 1 >= len(lines):
            return {"jobs": jobs, "error": None}

        # Parse header to find column positions
        header = lines[header_idx]
        col_positions = {}
        for col_name in ["Name", "Next", "Last", "Status", "Target", "Agent"]:
            idx = header.find(col_name)
            if idx >= 0:
                col_positions[col_name] = idx

        # Parse each data line using column positions
        for line in lines[header_idx + 1:]:
            if not line.strip():
                continue
            try:
                name_start = col_positions.get("Name", 37)
                next_start = col_positions.get("Next", 70)
                last_start = col_positions.get("Last", 81)
                status_start = col_positions.get("Status", 92)
                # Use Target column as status end boundary if present, else Agent
                status_end = col_positions.get("Target",
                             col_positions.get("Agent", 112))
                agent_start = col_positions.get("Agent", 112)

                name = line[name_start:next_start].strip().rstrip(".")[:22].strip()
                next_run = line[next_start:last_start].strip()
                last_run = line[last_start:status_start].strip()
                status_field = line[status_start:status_end].strip() if status_end else line[status_start:].split()[0]
                agent = line[agent_start:].strip().split()[0] if agent_start and len(line) > agent_start else ""

                # Normalize status
                status = "idle"
                status_lower = status_field.lower()
                if "error" in status_lower:
                    status = "error"
                elif "running" in status_lower:
                    status = "running"
                elif status_lower == "ok":
                    status = "ok"

                # Clean up last_run
                if last_run == "-":
                    last_run = ""

                jobs.append({
                    "name": name,
                    "status": status,
                    "last_run": last_run,
                    "next_run": next_run,
                    "agent": agent,
                })
            except (IndexError, KeyError):
                continue

    return {"jobs": jobs, "error": stderr if rc != 0 else None}


async def get_security_status() -> dict[str, Any]:
    """Get security status from various sources."""
    result: dict[str, Any] = {
        "ssh_intrusions": 0,
        "listening_ports": 0,
        "expected_ports": 4,
        "ufw_active": False,
        "fail2ban_active": False,
        "root_login_enabled": True,
    }

    stdout, _, rc = await run_command(
        "grep -c 'Failed password\\|Invalid user' /var/log/auth.log 2>/dev/null "
        "|| echo 0"
    )
    try:
        result["ssh_intrusions"] = int(stdout.strip())
    except ValueError:
        pass

    # Get detailed port info — prefer nmap, fall back to ss
    ports_list = []
    nmap_out, _, nmap_rc = await run_command(
        "nmap -sT -O localhost 2>/dev/null || nmap -sT localhost 2>/dev/null",
        timeout=15.0
    )
    if nmap_rc == 0 and "open" in nmap_out:
        for line in nmap_out.split("\n"):
            line = line.strip()
            if "/tcp" in line and "open" in line:
                parts = line.split()
                if len(parts) >= 3:
                    port = parts[0].split("/")[0]
                    state = parts[1]
                    service = parts[2] if len(parts) > 2 else "unknown"
                    ports_list.append({
                        "port": port,
                        "state": state,
                        "service": service,
                    })
    else:
        # Fallback to ss -tlnp
        ss_out, _, ss_rc = await run_command("ss -tlnp 2>/dev/null")
        if ss_rc == 0:
            for line in ss_out.strip().split("\n")[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4:
                    local_addr = parts[3]
                    # Extract port from address like *:22 or 0.0.0.0:22
                    port = local_addr.rsplit(":", 1)[-1] if ":" in local_addr else local_addr
                    # Try to get process name
                    process = ""
                    for p in parts:
                        if "users:" in p:
                            proc_match = re.search(r'"([^"]+)"', p)
                            if proc_match:
                                process = proc_match.group(1)
                            break
                    ports_list.append({
                        "port": port,
                        "state": "open",
                        "service": process or f"port-{port}",
                    })

    result["listening_ports"] = len(ports_list)
    result["ports_detail"] = ports_list

    stdout, _, _ = await run_command("ufw status 2>/dev/null || echo inactive")
    result["ufw_active"] = (
        "active" in stdout.lower() and "inactive" not in stdout.lower()
    )

    stdout, _, _ = await run_command(
        "systemctl is-active fail2ban 2>/dev/null || echo inactive"
    )
    result["fail2ban_active"] = stdout.strip() == "active"

    stdout, _, _ = await run_command(
        "grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null || echo 'yes'"
    )
    result["root_login_enabled"] = "no" not in stdout.lower()

    return result


async def get_network_activity() -> dict[str, Any]:
    """Parse ss -tnp to count active connections and extract peer IPs."""
    result: dict[str, Any] = {
        "active_connections": 0,
        "unique_ips": 0,
        "peer_ips": {},  # ip -> count
    }

    stdout, _, rc = await run_command("ss -tnp 2>/dev/null")
    if rc != 0 or not stdout.strip():
        return result

    ip_counts: dict[str, int] = {}
    for line in stdout.strip().split("\n")[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 5:
            # Peer address is column 4 (0-indexed)
            peer_addr = parts[4]
            # Extract IP from addr like 174.224.243.131:443 or [::1]:8080
            ip = peer_addr.rsplit(":", 1)[0] if ":" in peer_addr else peer_addr
            # Skip localhost and link-local
            if ip in ("127.0.0.1", "::1", "[::1]", "*", "0.0.0.0"):
                continue
            # Strip brackets from IPv6
            ip = ip.strip("[]")
            ip_counts[ip] = ip_counts.get(ip, 0) + 1

    total_conns = sum(ip_counts.values())
    result["active_connections"] = total_conns
    result["unique_ips"] = len(ip_counts)
    result["peer_ips"] = ip_counts

    return result


async def resolve_ip(ip: str, db=None) -> str:
    """Resolve an IP to hostname via dig -x. Uses DB cache with 24h TTL."""
    # Check cache first
    if db is not None:
        row = db.fetchone(
            "SELECT hostname, resolved_at FROM dns_cache WHERE ip = ?", (ip,)
        )
        if row and (time.time() - row["resolved_at"]) < 86400:
            return row["hostname"]

    # Async DNS resolution via dig
    stdout, _, rc = await run_command(f"dig -x {ip} +short +time=2 +tries=1 2>/dev/null", timeout=5.0)
    hostname = ""
    if rc == 0 and stdout.strip():
        # dig returns FQDN with trailing dot
        hostname = stdout.strip().split("\n")[0].rstrip(".")

    if not hostname:
        # Fallback to host command
        stdout, _, rc = await run_command(f"host {ip} 2>/dev/null", timeout=5.0)
        if rc == 0 and "domain name pointer" in stdout:
            match = re.search(r"pointer\s+(.+)\.", stdout)
            if match:
                hostname = match.group(1)

    if not hostname:
        hostname = "unknown"

    # Cache in DB
    if db is not None:
        db.execute(
            "INSERT OR REPLACE INTO dns_cache (ip, hostname, resolved_at) "
            "VALUES (?, ?, ?)",
            (ip, hostname, time.time()),
        )
        db.commit()

    return hostname


async def get_top_ips(network_data: dict, db=None, limit: int = 3) -> list[dict[str, Any]]:
    """Get top connected IPs with DNS resolution from network activity data."""
    peer_ips = network_data.get("peer_ips", {})
    if not peer_ips:
        return []

    # Sort by connection count descending
    sorted_ips = sorted(peer_ips.items(), key=lambda x: x[1], reverse=True)[:limit]

    results = []
    for ip, count in sorted_ips:
        hostname = await resolve_ip(ip, db=db)
        results.append({
            "ip": ip,
            "count": count,
            "hostname": hostname,
        })

    return results


async def get_ssh_login_summary() -> dict[str, Any]:
    """Parse /var/log/auth.log for SSH accepted/failed logins in last 24h."""
    result: dict[str, Any] = {
        "accepted": [],  # list of {ip, count, last_seen}
        "failed": [],    # list of {ip, count, last_seen}
    }

    # Get accepted SSH logins
    stdout, _, rc = await run_command(
        "grep 'Accepted' /var/log/auth.log 2>/dev/null | tail -500"
    )
    accepted_ips: dict[str, dict] = {}
    if rc == 0 and stdout.strip():
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            ip_match = re.search(r'from\s+(\d+\.\d+\.\d+\.\d+)', line)
            time_match = re.match(r'(\w+\s+\d+\s+\d+:\d+:\d+)', line)
            if ip_match:
                ip = ip_match.group(1)
                ts = time_match.group(1) if time_match else ""
                if ip not in accepted_ips:
                    accepted_ips[ip] = {"count": 0, "last_seen": ts}
                accepted_ips[ip]["count"] += 1
                accepted_ips[ip]["last_seen"] = ts

    # Get failed SSH logins
    stdout, _, rc = await run_command(
        "grep -E 'Failed password|Invalid user' /var/log/auth.log 2>/dev/null | tail -500"
    )
    failed_ips: dict[str, dict] = {}
    if rc == 0 and stdout.strip():
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            ip_match = re.search(r'from\s+(\d+\.\d+\.\d+\.\d+)', line)
            time_match = re.match(r'(\w+\s+\d+\s+\d+:\d+:\d+)', line)
            if ip_match:
                ip = ip_match.group(1)
                ts = time_match.group(1) if time_match else ""
                if ip not in failed_ips:
                    failed_ips[ip] = {"count": 0, "last_seen": ts}
                failed_ips[ip]["count"] += 1
                failed_ips[ip]["last_seen"] = ts

    # Sort by count, top 3
    for ip, info in sorted(accepted_ips.items(), key=lambda x: x[1]["count"], reverse=True)[:3]:
        result["accepted"].append({"ip": ip, "count": info["count"], "last_seen": info["last_seen"]})

    for ip, info in sorted(failed_ips.items(), key=lambda x: x[1]["count"], reverse=True)[:3]:
        result["failed"].append({"ip": ip, "count": info["count"], "last_seen": info["last_seen"]})

    return result


async def get_activity_log(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent activity from various log sources."""
    events: list[dict[str, Any]] = []

    stdout, _, rc = await run_command(
        "grep -E 'Accepted|session opened' /var/log/auth.log 2>/dev/null | tail -10"
    )
    if rc == 0:
        for line in stdout.strip().split("\n"):
            if line.strip():
                match = re.match(r"(\w+\s+\d+\s+\d+:\d+:\d+)", line)
                timestamp = match.group(1) if match else "unknown"
                events.append({
                    "time": timestamp,
                    "message": (
                        line[len(timestamp):].strip() if match else line
                    ),
                    "type": "ssh",
                    "level": "info",
                })

    stdout, _, rc = await run_command(
        "openclaw system events --limit 20 --json 2>/dev/null "
        "|| openclaw system events --limit 20 2>/dev/null"
    )
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                for event in data:
                    events.append({
                        "time": event.get(
                            "time", event.get("timestamp", "unknown")
                        ),
                        "message": event.get(
                            "message", event.get("text", str(event))
                        ),
                        "type": event.get("type", "openclaw"),
                        "level": event.get("level", "info"),
                    })
        except json.JSONDecodeError:
            for line in stdout.strip().split("\n")[:20]:
                if line.strip():
                    events.append({
                        "time": datetime.now().strftime("%H:%M"),
                        "message": line.strip(),
                        "type": "openclaw",
                        "level": "info",
                    })

    return events[:limit]


# ── Geo rate-limiter (1 request/sec for ip-api.com) ──
_geo_last_request = 0.0
_geo_lock = asyncio.Lock()


async def get_ip_geolocation(ip: str, db=None) -> dict[str, str]:
    """Fetch IP geolocation from ip-api.com. Cached 7 days in geo_cache table."""
    global _geo_last_request

    # Check cache first
    if db is not None:
        row = db.fetchone(
            "SELECT country_code, city, isp, resolved_at FROM geo_cache WHERE ip = ?",
            (ip,),
        )
        if row and (time.time() - row["resolved_at"]) < 7 * 86400:
            return {
                "country_code": row["country_code"],
                "city": row["city"],
                "isp": row["isp"],
            }

    result = {"country_code": "?", "city": "", "isp": ""}

    # Rate limit: 1 req/sec
    async with _geo_lock:
        now = time.time()
        wait = 1.0 - (now - _geo_last_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _geo_last_request = time.time()

    # Fetch from ip-api.com using urllib (pure stdlib)
    try:
        url = f"http://ip-api.com/json/{ip}?fields=country,countryCode,city,isp"
        req = urllib.request.Request(url, headers={"User-Agent": "GalacticCIC/1.0"})

        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=5)
            ),
            timeout=5.0,
        )
        data = json.loads(response.read().decode())
        result["country_code"] = data.get("countryCode", "?")
        result["city"] = data.get("city", "")
        result["isp"] = data.get("isp", "")
    except Exception:
        pass

    # Cache in DB
    if db is not None:
        db.execute(
            "INSERT OR REPLACE INTO geo_cache (ip, country_code, city, isp, resolved_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (ip, result["country_code"], result["city"], result["isp"], time.time()),
        )
        db.commit()

    return result


async def scan_attacker_ip(ip: str, db=None) -> dict[str, str]:
    """Nmap scan a single attacker IP. Cached 6h in attacker_scans table."""
    # Check cache first
    if db is not None:
        row = db.fetchone(
            "SELECT open_ports, os_guess, scanned_at FROM attacker_scans WHERE ip = ?",
            (ip,),
        )
        if row and (time.time() - row["scanned_at"]) < 6 * 3600:
            return {
                "open_ports": row["open_ports"],
                "os_guess": row["os_guess"],
            }

    result = {"open_ports": "", "os_guess": ""}

    stdout, stderr, rc = await run_command(
        f"nmap -sT --top-ports 20 {ip} 2>/dev/null", timeout=10.0
    )
    if rc == 0 and stdout:
        ports = []
        for line in stdout.split("\n"):
            line = line.strip()
            if "/tcp" in line and "open" in line:
                port = line.split("/")[0]
                ports.append(port)
        result["open_ports"] = ",".join(ports)

        # Try to parse OS guess
        for line in stdout.split("\n"):
            if "OS details:" in line or "Running:" in line:
                os_info = line.split(":", 1)[1].strip()
                result["os_guess"] = os_info[:30]
                break
        if not result["os_guess"]:
            # Guess from service banners
            if any(p in ports for p in ["22"]):
                result["os_guess"] = "Linux"

    # Cache in DB
    if db is not None:
        db.execute(
            "INSERT OR REPLACE INTO attacker_scans (ip, open_ports, os_guess, scanned_at) "
            "VALUES (?, ?, ?, ?)",
            (ip, result["open_ports"], result["os_guess"], time.time()),
        )
        db.commit()

    return result


async def get_openclaw_logs(limit: int = 20) -> list[dict[str, Any]]:
    """Tail openclaw logs from filesystem or CLI."""
    events: list[dict[str, Any]] = []

    # Try filesystem first
    log_dir = os.path.expanduser("~/.openclaw/logs")
    stdout, _, rc = await run_command(
        f"tail -20 {log_dir}/*.log 2>/dev/null", timeout=5.0
    )
    if rc != 0 or not stdout.strip():
        # Fallback to openclaw CLI
        stdout, _, rc = await run_command(
            "openclaw logs 2>/dev/null", timeout=5.0
        )

    if rc == 0 and stdout.strip():
        for line in stdout.strip().split("\n")[-limit:]:
            line = line.strip()
            if not line or line.startswith("==>"):
                continue
            # Try to parse timestamp
            time_str = datetime.now().strftime("%H:%M")
            ts_match = re.match(
                r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})', line
            )
            if ts_match:
                try:
                    time_str = ts_match.group(1).split("T")[-1].split(" ")[-1][:5]
                except Exception:
                    pass
            # Detect level
            level = "info"
            line_lower = line.lower()
            if "error" in line_lower or "fail" in line_lower:
                level = "error"
            elif "warn" in line_lower:
                level = "warning"

            events.append({
                "time": time_str,
                "message": line[:80],
                "type": "openclaw",
                "level": level,
            })

    return events[-limit:]


async def get_error_summary(ssh_summary=None) -> list[dict[str, Any]]:
    """Aggregate errors from cron jobs, SSH failures, and openclaw logs."""
    errors: list[dict[str, Any]] = []

    # 1. Cron errors from openclaw cron list
    cron_data = await get_cron_jobs()
    for job in cron_data.get("jobs", []):
        if job.get("status") == "error":
            errors.append({
                "time": job.get("last_run", "??:??")[-5:],
                "message": f"{job['name']}: delivery failed",
                "type": "cron",
                "level": "error",
            })

    # 2. SSH failed summary
    if ssh_summary:
        for entry in ssh_summary.get("failed", []):
            ip = entry.get("ip", "?")
            count = entry.get("count", 0)
            if count >= 5:
                ts = entry.get("last_seen", "")
                time_str = ts[-8:-3] if len(ts) >= 8 else "??:??"
                errors.append({
                    "time": time_str,
                    "message": f"{count} failed attempts from {ip}",
                    "type": "ssh",
                    "level": "error",
                })

    # 3. Openclaw log errors
    oc_logs = await get_openclaw_logs(limit=20)
    for ev in oc_logs:
        if ev.get("level") == "error":
            errors.append(ev)

    return errors


async def get_top_processes(count: int = 5) -> list[dict[str, Any]]:
    """Get top processes sorted by CPU usage.

    Returns list of dicts: pid, user, cpu, mem, command.
    """
    stdout, stderr, rc = await run_command(
        f"ps aux --sort=-%cpu | head -{count + 1}"
    )
    if rc != 0 or not stdout.strip():
        return []

    lines = stdout.strip().split("\n")
    if len(lines) < 2:
        return []

    processes = []
    for line in lines[1:]:  # Skip ps header
        parts = line.split(None, 10)
        if len(parts) >= 11:
            processes.append({
                "pid": parts[1],
                "user": parts[0][:8],
                "cpu": parts[2],
                "mem": parts[3],
                "command": parts[10].split("/")[-1][:20],
            })
    return processes


async def get_channels_status() -> list[dict[str, str]]:
    """Parse channel status from 'openclaw status' output."""
    stdout, stderr, rc = await run_command("openclaw status 2>/dev/null")
    if rc != 0 or not stdout:
        return []

    channels = []
    in_channels = False
    for line in stdout.splitlines():
        if "Channels" in line and "│" not in line:
            in_channels = True
            continue
        if in_channels:
            # Stop at next section
            if line.strip() and not line.strip().startswith("│") and not line.strip().startswith("├") and not line.strip().startswith("└") and not line.strip().startswith("┌") and not line.strip().startswith("─"):
                if "Sessions" in line or "Security" in line or "FAQ" in line:
                    break
            m = re.match(r"│\s*(\S+)\s*│\s*(\S+)\s*│\s*(\S+)\s*│\s*(.*?)\s*│", line)
            if m:
                name = m.group(1).strip()
                if name in ("Channel", "─", "──") or name.startswith("─"):
                    continue
                channels.append({
                    "name": name,
                    "enabled": m.group(2).strip(),
                    "state": m.group(3).strip(),
                    "detail": m.group(4).strip(),
                })
    return channels


async def get_update_status() -> dict[str, Any]:
    """Check for OpenClaw updates from 'openclaw status' output."""
    result = {"available": False, "current": "", "latest": ""}

    stdout, stderr, rc = await run_command("openclaw status 2>/dev/null")
    if rc != 0 or not stdout:
        return result

    for line in stdout.splitlines():
        # Check overview table for update info
        if "Update" in line and "available" in line:
            result["available"] = True
            m = re.search(r"update ([\d.]+(?:-\d+)?)", line)
            if m:
                result["latest"] = m.group(1)
        # Get current version from Gateway line
        if "Gateway" in line and "app " in line:
            m = re.search(r"app ([\d.]+(?:-\d+)?)", line)
            if m:
                result["current"] = m.group(1)

    # Also try --version for current
    if not result["current"]:
        stdout, stderr, rc = await run_command("openclaw --version 2>/dev/null")
        if rc == 0 and stdout.strip():
            result["current"] = stdout.strip().split("\n")[0]

    return result


def build_action_items(cron_data, security_data, channels, update_info, server_health):
    """Generate action items from collected data."""
    items = []

    # Cron errors
    for job in cron_data.get("jobs", []):
        if job.get("status", "").lower() == "error":
            name = job.get("name", "Unknown")
            items.append({"severity": "error", "text": f"{name} cron failed"})

    # Security findings
    ssh = security_data.get("ssh_intrusions", 0)
    if ssh > 50:
        items.append({"severity": "error", "text": f"{ssh} SSH intrusion attempts"})

    ports = security_data.get("listening_ports", 0)
    expected = security_data.get("expected_ports", 4)
    if ports > expected + 2:
        items.append({"severity": "warn", "text": f"{ports} listening ports (expected ~{expected})"})

    # Update available
    if update_info.get("available"):
        items.append({"severity": "warn",
                      "text": f"OpenClaw update: {update_info.get('latest', '?')}"})

    # Channel warnings
    for ch in channels:
        if ch.get("state", "").upper() == "WARN":
            items.append({"severity": "warn",
                          "text": f"{ch['name']}: {ch.get('detail', 'warning')}"})

    # High resource usage
    cpu = server_health.get("cpu_percent", 0)
    mem = server_health.get("mem_percent", 0)
    disk = server_health.get("disk_percent", 0)
    if disk > 80:
        items.append({"severity": "warn", "text": f"Disk usage: {disk:.0f}%"})
    if mem > 80:
        items.append({"severity": "warn", "text": f"Memory usage: {mem:.0f}%"})
    if cpu > 90:
        items.append({"severity": "warn", "text": f"CPU usage: {cpu:.0f}%"})

    return items
