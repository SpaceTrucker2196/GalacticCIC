# GalacticCIC — Claw Information Center

[![CI](https://github.com/SpaceTrucker2196/cic-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/SpaceTrucker2196/cic-dashboard/actions/workflows/ci.yml)

An htop-style interactive terminal dashboard for OpenClaw operations monitoring. This is the bridge display for any OpenClaw deployment.

![Screenshot Placeholder](docs/screenshot.png)

## Features

- **Agent Fleet Status** — agents, sessions, models, token usage, tokens/hour, main agent marker
- **Server Health** — CPU, memory, disk with trend arrows, load, uptime, gateway
- **Cron Jobs** — all jobs with status icons, timing, errors
- **Security Status** — SSH, ports, firewall, services
- **Activity Log** — scrollable event log, color coded
- **Historical Database** — SQLite-based metrics storage with 30-day retention
- **Trend Analysis** — trend arrows comparing current vs 1-hour-ago values
- **Tokens/Hour** — rolling token usage rate per agent and total

## Install

### Quick Setup

```bash
./scripts/setup.sh
```

### Manual Install

```bash
pip install -e .
```

### As an OpenClaw Skill

Place this repository in your OpenClaw skills directory. The `SKILL.md` provides the skill definition.

## Usage

```bash
galactic_cic
# or
python3 -m galactic_cic
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh all panels |
| `1`-`5` | Focus specific panel |
| `Tab` | Cycle panels |
| `?` | Help overlay |
| `Esc` | Close dialogs |

### Data Storage

Metrics are stored in `~/.galactic_cic/metrics.db` (SQLite). Records are auto-pruned after 30 days.

## Architecture

- **Pure Python stdlib** — curses, sqlite3, asyncio, subprocess, json, re, os
- **No OpenClaw library imports** — all interaction via CLI subprocess calls
- **Graceful degradation** — works even if openclaw CLI is not installed

## Tests

See [TESTS.md](TESTS.md) for the full test checklist and run instructions.

```bash
# Run BDD tests
python3 -m behave tests/features/

# Run unit tests
python3 -m unittest tests/test_collectors.py -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run the tests: `python3 -m behave tests/features/`
4. Submit a pull request

## License

MIT — see [LICENSE](LICENSE)
