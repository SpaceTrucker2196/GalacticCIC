"""Async data collectors for GalacticCIC — shells out to system commands."""

import asyncio
import json
import re
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

    # CPU from /proc/stat
    stdout1, _, _ = await run_command("head -1 /proc/stat")
    await asyncio.sleep(0.1)
    stdout2, _, _ = await run_command("head -1 /proc/stat")

    try:
        cpu1 = [int(x) for x in stdout1.split()[1:8]]
        cpu2 = [int(x) for x in stdout2.split()[1:8]]
        idle1 = cpu1[3] + cpu1[4]
        idle2 = cpu2[3] + cpu2[4]
        total1 = sum(cpu1)
        total2 = sum(cpu2)
        total_diff = total2 - total1
        idle_diff = idle2 - idle1
        if total_diff > 0:
            result["cpu_percent"] = ((total_diff - idle_diff) / total_diff) * 100
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
        if len(lines) < 2:
            return {"jobs": jobs, "error": None}

        # Parse header to find column positions
        header = lines[0]
        col_positions = {}
        for col_name in ["Name", "Next", "Last", "Status", "Agent"]:
            idx = header.find(col_name)
            if idx >= 0:
                col_positions[col_name] = idx

        # Parse each data line using column positions
        for line in lines[1:]:
            if not line.strip():
                continue
            try:
                name_start = col_positions.get("Name", 37)
                next_start = col_positions.get("Next", 70)
                last_start = col_positions.get("Last", 81)
                status_start = col_positions.get("Status", 92)
                agent_start = col_positions.get("Agent", 112)

                name = line[name_start:next_start].strip().rstrip(".")
                next_run = line[next_start:last_start].strip()
                last_run = line[last_start:status_start].strip()
                status_field = line[status_start:agent_start].strip() if agent_start else line[status_start:].split()[0]
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
                    "name": name[:22],
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
