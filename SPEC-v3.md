# GalacticCIC v3 Spec — Historical Database & Trending

## Overview
Add a SQLite-based historical database to track metrics over time, enabling trend analysis, tokens/hour calculations, and historical dashboards.

## Key Requirements

### 1. Historical Database (SQLite)
- Location: `~/.galactic_cic/metrics.db`
- NO dependency on OpenClaw libraries — pure Python stdlib + sqlite3
- Record metrics every refresh cycle
- Tables:
  - `agent_metrics` — agent name, tokens, sessions, storage, timestamp
  - `server_metrics` — cpu, memory, disk, load, timestamp
  - `cron_metrics` — job name, status, last_run, next_run, timestamp
  - `security_metrics` — ssh_intrusions, ports_count, timestamp
  - `port_scans` — port, service, state, timestamp
- Retention: keep 30 days by default, auto-prune old records

### 2. Tokens Per Hour
- Calculate from agent_metrics history
- Show tokens/hour for each agent in the agent panel
- Show total tokens/hour across all agents
- Rolling window: last 1 hour of data

### 3. Main Agent Indicator
- In agent fleet panel, mark which agent is the "main" (default) agent
- Parse from `openclaw agents list` output (look for "(default)")

### 4. Trending Indicators
- For each metric, show trend arrows:
  - ↑ increasing, ↓ decreasing, → stable
- Compare current value to 1-hour-ago value
- Show in server health panel (CPU/MEM/DISK trends)
- Show in agent panel (token usage trends)

### 5. Externalized Code — No OpenClaw Library Dependencies
- ALL interaction with OpenClaw is via CLI subprocess calls only
- No `import openclaw` anywhere
- Pure Python stdlib: curses, sqlite3, asyncio, subprocess, json, re, os
- Works on any Linux server that has `openclaw` CLI installed
- Gracefully degrades if openclaw is not installed (shows "N/A")

### 6. Setup Script
Create `scripts/setup.sh` that:
```bash
#!/bin/bash
# GalacticCIC Setup Script
# Works on any Debian/Ubuntu system with OpenClaw installed

set -e

echo "🛸 GalacticCIC Setup"
echo "===================="

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required"
    exit 1
fi

# Check Python version >= 3.10
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PY_VER"

# Check for openclaw (warn but don't fail)
if command -v openclaw &>/dev/null; then
    OC_VER=$(openclaw --version 2>/dev/null || echo "unknown")
    echo "✅ OpenClaw $OC_VER"
else
    echo "⚠️  OpenClaw not found — dashboard will show limited data"
fi

# Check for nmap (optional)
if command -v nmap &>/dev/null; then
    echo "✅ nmap available"
else
    echo "ℹ️  nmap not found — port scanning will use ss instead"
fi

# Install galactic_cic
echo ""
echo "Installing GalacticCIC..."
pip install --break-system-packages -e . 2>/dev/null || pip install -e .

# Create data directory
mkdir -p ~/.galactic_cic
echo "✅ Data directory: ~/.galactic_cic"

# Verify installation
if command -v galactic_cic &>/dev/null; then
    echo ""
    echo "✅ GalacticCIC installed successfully!"
    echo "   Run: galactic_cic"
else
    echo ""
    echo "⚠️  galactic_cic not found in PATH"
    echo "   Try: python3 -m galactic_cic"
fi
```

### 7. Database Module Structure

```
src/galactic_cic/
├── db/
│   ├── __init__.py
│   ├── database.py      # SQLite connection, schema, migrations
│   ├── recorder.py      # Record metrics from collectors
│   └── trends.py        # Trend calculations, tokens/hour
```

### 8. Database Schema

```sql
CREATE TABLE IF NOT EXISTS agent_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    agent_name TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    sessions INTEGER DEFAULT 0,
    storage_bytes INTEGER DEFAULT 0,
    model TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS server_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    cpu_percent REAL DEFAULT 0,
    mem_used_mb REAL DEFAULT 0,
    mem_total_mb REAL DEFAULT 0,
    disk_used_gb REAL DEFAULT 0,
    disk_total_gb REAL DEFAULT 0,
    load_1m REAL DEFAULT 0,
    load_5m REAL DEFAULT 0,
    load_15m REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cron_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    job_name TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    last_run TEXT DEFAULT '',
    next_run TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS security_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    ssh_intrusions INTEGER DEFAULT 0,
    ports_open INTEGER DEFAULT 0,
    ufw_active INTEGER DEFAULT 0,
    fail2ban_active INTEGER DEFAULT 0,
    root_login_enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS port_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    port INTEGER NOT NULL,
    service TEXT DEFAULT '',
    state TEXT DEFAULT 'open'
);

CREATE INDEX idx_agent_ts ON agent_metrics(timestamp);
CREATE INDEX idx_server_ts ON server_metrics(timestamp);
CREATE INDEX idx_security_ts ON security_metrics(timestamp);
```

### 9. Updated Panel Displays

**Agent Fleet Panel:**
```
  AGENT        MODEL          STOR  TOKENS  TOK/H  S
  main*        opus-4-6       27M   126k    42k/h  3
  rentalops    opus-4-6       274M  65k     12k/h  4
  raven        opus-4-6       188K  168k    28k/h  5
  
  Total: 359k tokens  82k/h  12 sessions
  Gateway: running  v2026.2.21-2
```

**Server Health Panel (with trends):**
```
  CPU:  ████░░░░░░  23% →
  MEM:  ██████░░░░  58% ↑  3.2G/5.5G
  DISK: ████████░░  79% →  32G/40G
  LOAD: 0.42 0.38 0.31
  UP:   2d 14h 23m
```

## Implementation Notes
- Database writes happen async in background, never block the UI
- Use WAL mode for SQLite (concurrent reads during writes)
- Trend calculations use simple linear comparison (now vs 1h ago)
- tokens/hour = (current_tokens - tokens_1h_ago) / 1.0
- If no historical data yet, show "--" for trends
- Auto-create ~/.galactic_cic/ on first run
- DB migrations: version table, auto-upgrade schema
