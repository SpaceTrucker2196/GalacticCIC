# GalacticCIC — Claw Information Center

A Fallout-inspired green phosphor terminal dashboard for monitoring OpenClaw multi-agent deployments. Built with pure Python curses — no external UI dependencies.

## What It Does

GalacticCIC gives you a single-screen view of your entire OpenClaw operation:

- **Agent Fleet** — all agents, models, sessions, token usage, tokens/hour trends
- **Server Health** — CPU/MEM/DISK/NET sparklines with 24h averages, load, uptime, top processes
- **Cron Jobs** — status, timing, consecutive error tracking
- **Security** — SSH login/intrusion monitoring, port scanning, attacker nmap reconnaissance, geolocation
- **Activity Log** — real-time event stream from OpenClaw logs, SSH, cron
- **SITREP** — channel health (Discord/WhatsApp), update status, aggregated action items
- **Historical Metrics** — SQLite database with 30-day retention, trend arrows, sparklines pre-populated from history

All data collection runs as a background systemd daemon. The dashboard is a read-only view that never runs commands itself.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    gcic dashboard (TUI)                      │
│  Reads from SQLite — never runs openclaw commands directly   │
└──────────────────────────┬──────────────────────────────────┘
                           │ reads ~/.galactic_cic/metrics.db
┌──────────────────────────┴──────────────────────────────────┐
│              galactic-cic-collector (daemon)                  │
│  Tiered async collection: 30s / 2min / 5min / 15min          │
│  Runs: openclaw agents/cron/status, df, free, ss, nmap, etc. │
│  Writes metrics to SQLite                                     │
│  systemd user service — auto-starts, survives logout          │
└─────────────────────────────────────────────────────────────┘
```

### Layout (wide terminal ≥120 cols)

```
┌─ Agent Fleet ──────┬──────────── SITREP ──────────────────┐
│ agents, models,    │ channels, update status, action items │
│ sessions, tokens   │                                      │
├─ Cron Jobs ────────┼─ Server Health ──┬─ Security ────────┤
│ status, timing,    │ sparklines, load │ SSH, ports, nmap  │
│ error tracking     │ processes, IPs   │ attacker scans    │
├──────────────── Activity Log ─────────────────────────────┤
│ real-time events, errors, OpenClaw logs                    │
└───────────────────────────────────────────────────────────┘
```

Falls back to 2-column at <120 cols.

## Install

```bash
# Clone
git clone https://github.com/SpaceTrucker2196/cic-dashboard.git
cd cic-dashboard

# Install (editable)
pip install -e . --break-system-packages

# Install the systemd collector service
gcic install

# Start collecting data
gcic start
```

## Commands

All commands start with `gcic`:

| Command | Description |
|---------|-------------|
| `gcic start` | Start the collector daemon |
| `gcic stop` | Stop the collector daemon |
| `gcic restart` | Restart the collector daemon |
| `gcic status` | Show daemon status, PID, memory + DB stats per table |
| `gcic dashboard` | Launch the interactive TUI |
| `gcic collect` | Run a single collection cycle (manual/debug) |
| `gcic db` | Show database statistics |
| `gcic db prune` | Prune records older than 30 days |
| `gcic db path` | Print database file path |
| `gcic logs` | Show last 30 lines of collector logs |
| `gcic logs -f` | Follow collector logs in real-time |
| `gcic logs -n 100` | Show last N lines of logs |
| `gcic install` | Install/reinstall the systemd user service |
| `gcic version` | Show version |

Legacy commands also work: `galactic-cic` launches the dashboard directly.

### Keyboard Controls (in dashboard)

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh all panels |
| `1`–`6` | Focus specific panel |
| `Tab` | Cycle panel focus |
| `t` | Cycle theme (phosphor → amber → blue) |
| `?` | Help overlay |

## Data Collection

The collector daemon runs independently of the dashboard with tiered scheduling:

| Tier | Interval | Sources |
|------|----------|---------|
| Fast | 30s | Server health, top processes |
| Medium | 2 min | Cron jobs, activity log, OpenClaw logs, network |
| Slow | 5 min | Agents, OpenClaw status, security, channels, update |
| Glacial | 15 min | DNS resolution, IP geolocation, attacker nmap scans |

All data is stored in `~/.galactic_cic/metrics.db` (SQLite). Records auto-prune after 30 days.

### What Gets Cached

| Table | Contents |
|-------|----------|
| `server_metrics` | CPU, memory, disk, load averages |
| `agent_metrics` | Tokens used, sessions, storage per agent |
| `cron_metrics` | Job status, last/next run times |
| `security_metrics` | SSH intrusions, open ports, firewall status |
| `network_metrics` | Active connections, unique IPs |
| `dns_cache` | IP → hostname resolution (24h TTL) |
| `geo_cache` | IP → country/city/ISP geolocation |
| `attacker_scans` | Nmap results for failed SSH login IPs |
| `sitrep_cache` | Channel status, update info, action items |

## Themes

Three built-in themes, switchable at runtime with `t`:

- **Phosphor** — Classic green-on-black (default)
- **Amber** — Yellow/orange terminal style
- **Blue** — Cyan terminal style

Theme preference is saved to `~/.galactic_cic/config.json`.

## Testing

```bash
# Unit tests (135 tests — all mock data, no server needed)
python3 -m unittest tests.test_panels tests.test_collectors -v

# BDD scenarios (25 scenarios, 83 steps)
pip install behave
python3 -m behave tests/features/
```

### Test Coverage

- **106 panel tests** — every panel render, theme switching, sparklines, tables, SITREP, nmap indicators
- **29 collector tests** — command execution, parsing, size conversion, database CRUD, trend calculations
- **25 BDD scenarios** — agent display, server thresholds, cron errors, security alerts, activity log, navigation, install verification

All tests use mock data — no live server, no OpenClaw CLI, no curses terminal required.

## Tech Stack

- **Python 3.12+** — curses, asyncio, sqlite3, subprocess, json, re
- **Zero external dependencies** — pure stdlib (no Rich, no Textual, no requests)
- **systemd user services** — auto-start, restart on failure, survives logout via linger
- **OpenClaw integration** — all via CLI subprocess calls, graceful degradation if unavailable

## Project Structure

```
src/galactic_cic/
├── app.py               # Main curses TUI application
├── cli.py               # gcic CLI entry point
├── collector_daemon.py   # Background data collection daemon
├── theme.py             # Color theme system (phosphor/amber/blue)
├── data/
│   └── collectors.py    # Async data collectors (openclaw CLI, system commands)
├── db/
│   ├── database.py      # SQLite schema, connection, queries
│   ├── recorder.py      # Write collected data to database
│   └── trends.py        # Trend calculations (arrows, tokens/hour)
└── panels/
    ├── base.py          # BasePanel, StyledText, Table classes
    ├── agents.py        # Agent Fleet panel
    ├── server.py        # Server Health panel (sparklines, processes)
    ├── cron.py          # Cron Jobs panel
    ├── security.py      # Security panel (SSH, nmap, geolocation)
    ├── activity.py      # Activity Log panel
    └── sitrep.py        # SITREP panel (channels, updates, action items)
```

## Build History

Built iteratively through AI-assisted development:

1. **v1** — Textual-based TUI (abandoned — grey background issues, internal method conflicts)
2. **v2** — Curses rewrite with green phosphor theme, BDD test suite
3. **v3** — SQLite historical database, trend arrows, tokens/hour, Tufte sparklines
4. **v3.1** — SITREP panel (3-column layout), standalone collector daemon, `gcic` CLI, attacker nmap scanning, SITREP caching, historical sparkline pre-population, theme system

## License

MIT — see [LICENSE](LICENSE)
