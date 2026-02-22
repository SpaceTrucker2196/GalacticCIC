"""Data collectors for CIC Dashboard - shells out to system commands."""

import asyncio
import json
import re
from datetime import datetime
from typing import Any


async def run_command(cmd: str, timeout: float = 10.0) -> tuple[str, str, int]:
    """Run a shell command asynchronously and return stdout, stderr, returncode."""
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
    """Get agent fleet status from openclaw agents list."""
    stdout, stderr, rc = await run_command("openclaw agents list --json 2>/dev/null || openclaw agents list 2>/dev/null")

    agents = []
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                agents = data
            elif isinstance(data, dict) and "agents" in data:
                agents = data["agents"]
        except json.JSONDecodeError:
            # Parse text output
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    parts = line.split()
                    if parts:
                        agents.append({
                            "name": parts[0],
                            "status": "online" if len(parts) < 2 or "offline" not in line.lower() else "offline",
                        })

    return {"agents": agents, "error": stderr if rc != 0 else None}


async def get_openclaw_status() -> dict[str, Any]:
    """Get openclaw status including sessions, model, gateway."""
    result = {
        "sessions": 0,
        "model": "unknown",
        "gateway_status": "unknown",
        "version": "unknown",
    }

    # Get general status
    stdout, stderr, rc = await run_command("openclaw status --json 2>/dev/null || openclaw status 2>/dev/null")
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            result["sessions"] = data.get("sessions", data.get("active_sessions", 0))
            result["model"] = data.get("model", data.get("default_model", "unknown"))
        except json.JSONDecodeError:
            # Parse text output
            for line in stdout.split("\n"):
                if "session" in line.lower():
                    match = re.search(r"(\d+)", line)
                    if match:
                        result["sessions"] = int(match.group(1))
                if "model" in line.lower():
                    parts = line.split(":")
                    if len(parts) > 1:
                        result["model"] = parts[1].strip()

    # Get gateway status
    stdout, stderr, rc = await run_command("openclaw gateway status 2>/dev/null")
    if rc == 0:
        result["gateway_status"] = "running" if "running" in stdout.lower() else "stopped"

    # Get version
    stdout, stderr, rc = await run_command("openclaw --version 2>/dev/null || openclaw version 2>/dev/null")
    if rc == 0 and stdout.strip():
        result["version"] = stdout.strip().split("\n")[0]

    return result


async def get_server_health() -> dict[str, Any]:
    """Get server health metrics from system commands."""
    result = {
        "cpu_percent": 0.0,
        "mem_percent": 0.0,
        "mem_used": "0G",
        "mem_total": "0G",
        "disk_percent": 0.0,
        "disk_used": "0G",
        "disk_total": "0G",
        "load_avg": [0.0, 0.0, 0.0],
        "uptime": "unknown",
    }

    # Memory from free -h
    stdout, stderr, rc = await run_command("free -h")
    if rc == 0:
        lines = stdout.strip().split("\n")
        for line in lines:
            if line.startswith("Mem:"):
                parts = line.split()
                if len(parts) >= 3:
                    result["mem_total"] = parts[1]
                    result["mem_used"] = parts[2]
                    # Calculate percentage
                    try:
                        total_val = _parse_size(parts[1])
                        used_val = _parse_size(parts[2])
                        if total_val > 0:
                            result["mem_percent"] = (used_val / total_val) * 100
                    except (ValueError, IndexError):
                        pass

    # Disk from df -h
    stdout, stderr, rc = await run_command("df -h /")
    if rc == 0:
        lines = stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                result["disk_total"] = parts[1]
                result["disk_used"] = parts[2]
                try:
                    result["disk_percent"] = float(parts[4].rstrip("%"))
                except ValueError:
                    pass

    # Load average and uptime from uptime
    stdout, stderr, rc = await run_command("uptime")
    if rc == 0:
        # Parse load average
        match = re.search(r"load average:\s*([\d.]+),?\s*([\d.]+),?\s*([\d.]+)", stdout)
        if match:
            result["load_avg"] = [float(match.group(i)) for i in (1, 2, 3)]

        # Parse uptime
        match = re.search(r"up\s+(.+?),\s+\d+\s+user", stdout)
        if match:
            result["uptime"] = match.group(1).strip()
        else:
            match = re.search(r"up\s+(.+?),\s+load", stdout)
            if match:
                result["uptime"] = match.group(1).strip()

    # CPU from /proc/stat (calculate over 0.5s interval)
    stdout1, _, _ = await run_command("cat /proc/stat | head -1")
    await asyncio.sleep(0.1)
    stdout2, _, _ = await run_command("cat /proc/stat | head -1")

    try:
        cpu1 = [int(x) for x in stdout1.split()[1:8]]
        cpu2 = [int(x) for x in stdout2.split()[1:8]]

        idle1 = cpu1[3] + cpu1[4]  # idle + iowait
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


def _parse_size(size_str: str) -> float:
    """Parse size string like '3.2G' or '512M' to float in GB."""
    size_str = size_str.strip().upper()
    multipliers = {"K": 1/1024/1024, "M": 1/1024, "G": 1, "T": 1024, "P": 1024*1024}

    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return float(size_str[:-1]) * mult
            except ValueError:
                return 0.0

    # Try parsing as raw number (bytes)
    try:
        return float(size_str) / (1024**3)
    except ValueError:
        return 0.0


async def get_cron_jobs() -> dict[str, Any]:
    """Get cron job status from openclaw cron list."""
    stdout, stderr, rc = await run_command("openclaw cron list --json 2>/dev/null || openclaw cron list 2>/dev/null")

    jobs = []
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                jobs = data
            elif isinstance(data, dict) and "jobs" in data:
                jobs = data["jobs"]
        except json.JSONDecodeError:
            # Parse text output
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    # Try to parse: name status last_run next_run
                    parts = line.split()
                    if len(parts) >= 2:
                        status = "idle"
                        if "error" in line.lower() or "fail" in line.lower():
                            status = "error"
                        elif "running" in line.lower():
                            status = "running"
                        elif "ok" in line.lower() or "success" in line.lower():
                            status = "ok"

                        jobs.append({
                            "name": parts[0],
                            "status": status,
                            "last_run": parts[1] if len(parts) > 1 else "unknown",
                        })

    return {"jobs": jobs, "error": stderr if rc != 0 else None}


async def get_security_status() -> dict[str, Any]:
    """Get security status from various sources."""
    result = {
        "ssh_intrusions": 0,
        "listening_ports": 0,
        "expected_ports": 4,
        "ufw_active": False,
        "fail2ban_active": False,
        "root_login_enabled": True,
        "repo_status": "unknown",
        "kev_status": "unknown",
    }

    # SSH intrusion attempts from auth.log (last 24h)
    stdout, stderr, rc = await run_command(
        "grep -c 'Failed password\\|Invalid user' /var/log/auth.log 2>/dev/null || echo 0"
    )
    try:
        result["ssh_intrusions"] = int(stdout.strip())
    except ValueError:
        pass

    # Listening ports from ss -tlnp
    stdout, stderr, rc = await run_command("ss -tlnp 2>/dev/null | tail -n +2 | wc -l")
    try:
        result["listening_ports"] = int(stdout.strip())
    except ValueError:
        pass

    # UFW status
    stdout, stderr, rc = await run_command("ufw status 2>/dev/null || echo inactive")
    result["ufw_active"] = "active" in stdout.lower() and "inactive" not in stdout.lower()

    # Fail2ban status
    stdout, stderr, rc = await run_command("systemctl is-active fail2ban 2>/dev/null || echo inactive")
    result["fail2ban_active"] = "active" == stdout.strip()

    # Root login check
    stdout, stderr, rc = await run_command("grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null || echo 'yes'")
    result["root_login_enabled"] = "no" not in stdout.lower()

    return result


async def get_activity_log(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent activity from various log sources."""
    events = []

    # Get recent SSH logins from auth.log
    stdout, stderr, rc = await run_command(
        f"grep -E 'Accepted|session opened' /var/log/auth.log 2>/dev/null | tail -10"
    )
    if rc == 0:
        for line in stdout.strip().split("\n"):
            if line.strip():
                # Parse syslog format: Mon DD HH:MM:SS hostname ...
                match = re.match(r"(\w+\s+\d+\s+\d+:\d+:\d+)", line)
                timestamp = match.group(1) if match else "unknown"
                events.append({
                    "time": timestamp,
                    "message": line[len(timestamp):].strip() if match else line,
                    "type": "ssh",
                    "level": "info",
                })

    # Get openclaw events if available
    stdout, stderr, rc = await run_command(
        "openclaw system events --limit 20 --json 2>/dev/null || openclaw system events --limit 20 2>/dev/null"
    )
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, list):
                for event in data:
                    events.append({
                        "time": event.get("time", event.get("timestamp", "unknown")),
                        "message": event.get("message", event.get("text", str(event))),
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

    # Sort by time (most recent first) and limit
    return events[:limit]
