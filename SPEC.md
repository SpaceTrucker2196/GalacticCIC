# CIC Dashboard — Combat Information Center TUI

## Overview
An htop-style interactive terminal dashboard for OpenClaw operations monitoring. This is the bridge display for the Spacetrucker Galactic operations center.

## Tech Stack
- **Python 3** with **Textual** framework (modern async TUI)
- **Rich** for styled text rendering
- Data sourced from `openclaw` CLI commands and system tools

## Layout (4-panel design)

```
┌─────────────────────────────────────────────────────────────┐
│  🛸 CIC — Combat Information Center    [19:47 UTC / 13:47 CT] │
├──────────────────────────┬──────────────────────────────────┤
│  AGENT FLEET STATUS      │  SERVER HEALTH                   │
│                          │                                  │
│  🛸 main     ● ONLINE   │  CPU:  ████░░░░░░  23%           │
│  🏠 rentalops ● ONLINE  │  MEM:  ██████░░░░  58%  3.2G/8G │
│  🪶 raven    ● ONLINE   │  DISK: ████████░░  79%  32G/40G  │
│                          │  LOAD: 0.42 0.38 0.31            │
│  Sessions: 19 active     │  UP:   2d 14h 23m                │
│  Model: claude-opus-4-6  │                                  │
├──────────────────────────┼──────────────────────────────────┤
│  CRON JOBS               │  SECURITY STATUS                 │
│                          │                                  │
│  ✅ Daily Backup    6h   │  SSH:  ✅ No intrusions           │
│  ✅ Harvey St      5h    │  Ports: ✅ 4 listening (expected) │
│  ❌ Deal Flow     err    │  Repo: ✅ Private + encrypted     │
│  ❌ Weather       err    │  KEV:  ✅ No relevant vulns       │
│  ⏳ KEV Check     24h   │  UFW:  ⚠️  Inactive              │
│  ⏳ Log Audit     12h   │  Fail2ban: ❌ Inactive            │
│                          │  RootLogin: ⚠️  Enabled          │
├──────────────────────────┴──────────────────────────────────┤
│  ACTIVITY LOG                                               │
│  19:47 Deal Flow Scanner completed — 22 listings, 2 hot    │
│  19:02 Heartbeat check — all systems nominal                │
│  17:56 SSH login from 96.42.52.151 (spacetrucker)           │
│  16:00 OpenClaw update check — 2026.2.21-2 available        │
└─────────────────────────────────────────────────────────────┘
```

## Panels

### 1. Agent Fleet Status (top-left)
- List all agents with online/offline status
- Active session count per agent
- Current model
- Token usage for active sessions (bar chart)
- Data: `openclaw agents list`, `openclaw status`

### 2. Server Health (top-right)
- CPU usage (bar + percentage)
- Memory usage (bar + used/total)
- Disk usage (bar + used/total)
- Load average
- Uptime
- OpenClaw gateway status (running/stopped)
- OpenClaw version
- Data: `free`, `df`, `uptime`, `openclaw gateway status`

### 3. Cron Jobs (middle-left)
- All cron jobs with status icons: ✅ ok, ❌ error, ⏳ idle, 🔄 running
- Time since last run
- Next run time
- Consecutive error count (if any)
- Data: `openclaw cron list`

### 4. Security Status (middle-right)
- SSH intrusion attempts (last 24h count)
- Listening ports (count + expected vs actual)
- Repo security (last validation result)
- CISA KEV status (last check result)
- UFW status
- Fail2ban status
- PermitRootLogin status
- Data: `/var/log/auth.log`, `ss -tlnp`, security scripts

### 5. Activity Log (bottom, full width)
- Scrollable log of recent events
- Sources: cron completions, SSH logins, heartbeat results, alerts
- Color coded: green=ok, yellow=warn, red=error
- Data: cron run logs, auth.log, openclaw logs

## Interaction
- **q** — Quit
- **r** — Force refresh all panels
- **1-5** — Focus/expand a specific panel
- **Tab** — Cycle focus between panels
- **/** — Filter activity log
- **?** — Help overlay

## Refresh Rates
- Server health: every 5 seconds
- Agent/cron status: every 30 seconds
- Security: every 60 seconds
- Activity log: every 10 seconds

## Colors / Theme
- Dark background (terminal default)
- Green: healthy/ok
- Yellow/amber: warning
- Red: error/critical
- Cyan: informational
- Header: bold white on dark blue

## Install & Run
```bash
pip install textual rich
python cic.py
```

## File Structure
```
cic-dashboard/
├── SPEC.md
├── cic.py          # Main app entry point
├── panels/
│   ├── agents.py   # Agent fleet panel
│   ├── server.py   # Server health panel
│   ├── cron.py     # Cron jobs panel
│   ├── security.py # Security status panel
│   └── activity.py # Activity log panel
├── data/
│   └── collectors.py  # Data collection functions
└── requirements.txt
```
