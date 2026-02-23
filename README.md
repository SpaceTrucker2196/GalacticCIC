# GalacticCIC — Claw Information Center

[![CI](https://github.com/SpaceTrucker2196/cic-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/SpaceTrucker2196/cic-dashboard/actions/workflows/ci.yml)

An htop-style interactive terminal dashboard for OpenClaw operations monitoring. This is the bridge display for any OpenClaw deployment.

![Screenshot Placeholder](docs/screenshot.png)

## Features

- **Agent Fleet Status** — agents, sessions, models, token usage
- **Server Health** — CPU, memory, disk, load, uptime, gateway
- **Cron Jobs** — all jobs with status icons, timing, errors
- **Security Status** — SSH, ports, firewall, services
- **Activity Log** — scrollable event log, color coded

## Install

### Quick Install

```bash
./scripts/install.sh
```

### Manual Install

```bash
pip install textual rich
pip install -e .
```

### As an OpenClaw Skill

Place this repository in your OpenClaw skills directory. The `SKILL.md` provides the skill definition.

## Usage

```bash
python3 -m galactic_cic
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Force refresh all panels |
| `1`-`5` | Focus specific panel |
| `Tab` | Cycle panels |
| `/` | Filter activity log |
| `?` | Help overlay |
| `Esc` | Close dialogs / clear filter |

## Tests

See [TESTS.md](TESTS.md) for the full test checklist and run instructions.

```bash
# Run BDD tests
cd tests && behave

# Run unit tests
cd tests && python -m unittest test_collectors -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run the tests: `cd tests && behave`
4. Submit a pull request

## License

MIT — see [LICENSE](LICENSE)
