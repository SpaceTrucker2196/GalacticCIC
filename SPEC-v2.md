# GalacticCIC — Combat Information Center TUI (v2 Spec)

## Overview
An htop-style interactive terminal dashboard for OpenClaw operations monitoring. Installable as an OpenClaw skill on any instance. This is the bridge display for any OpenClaw deployment.

## Tech Stack
- **Python 3** with **Textual** framework (modern async TUI)
- **Rich** for styled text rendering
- **behave** for Cucumber-style BDD tests
- Data sourced from `openclaw` CLI commands and system tools

## OpenClaw Skill Packaging

This project MUST be installable as an OpenClaw skill. Structure:

```
GalacticCIC/
├── SKILL.md                    # OpenClaw skill definition (YAML frontmatter + instructions)
├── README.md                   # Full README with badges, install, usage, links
├── TESTS.md                    # Checklist of all tests with status
├── LICENSE                     # MIT
├── requirements.txt            # Python dependencies
├── setup.py                    # pip installable
├── scripts/
│   └── install.sh              # Auto-install script (pip install deps, verify openclaw)
├── src/
│   └── galactic_cic/
│       ├── __init__.py
│       ├── app.py              # Main Textual app entry point
│       ├── panels/
│       │   ├── __init__.py
│       │   ├── agents.py       # Agent fleet panel
│       │   ├── server.py       # Server health panel
│       │   ├── cron.py         # Cron jobs panel
│       │   ├── security.py     # Security status panel
│       │   └── activity.py     # Activity log panel
│       └── data/
│           ├── __init__.py
│           └── collectors.py   # Async data collection functions
├── tests/
│   ├── features/
│   │   ├── agents.feature      # Cucumber: agent fleet display
│   │   ├── server.feature      # Cucumber: server health display
│   │   ├── cron.feature        # Cucumber: cron job display
│   │   ├── security.feature    # Cucumber: security status
│   │   ├── activity.feature    # Cucumber: activity log
│   │   ├── navigation.feature  # Cucumber: keyboard navigation
│   │   └── install.feature     # Cucumber: installation
│   ├── steps/
│   │   ├── agents_steps.py
│   │   ├── server_steps.py
│   │   ├── cron_steps.py
│   │   ├── security_steps.py
│   │   ├── activity_steps.py
│   │   ├── navigation_steps.py
│   │   └── install_steps.py
│   ├── environment.py          # behave test environment setup
│   └── test_collectors.py      # Unit tests for data collectors
├── .github/
│   └── workflows/
│       ├── ci.yml              # Build, lint, test on push/PR
│       └── release.yml         # Build + publish on tag
└── .gitignore
```

### SKILL.md Format
```yaml
---
name: galactic-cic
description: |
  Interactive htop-style terminal dashboard for OpenClaw operations monitoring.
  Displays agent fleet status, server health, cron jobs, security posture, and
  activity logs in real-time. Launch with: python3 -m galactic_cic
  Use when the user wants to monitor their OpenClaw deployment, check agent status,
  view cron job health, or get a security overview from the terminal.
metadata:
  author: SpaceTrucker2196
  version: "1.0.0"
  openclaw:
    emoji: "🛸"
    requires:
      anyBins: ["python3"]
      pip: ["textual", "rich"]
---
```

## Layout (5-panel design)

Same as original SPEC.md layout with these panels:
1. **Agent Fleet Status** (top-left) — agents, sessions, models, token usage
2. **Server Health** (top-right) — CPU, memory, disk, load, uptime, gateway
3. **Cron Jobs** (middle-left) — all jobs with status icons, timing, errors
4. **Security Status** (middle-right) — SSH, ports, repo, KEV, services
5. **Activity Log** (bottom) — scrollable event log, color coded

## Data Collectors

All data collection via async subprocess calls to:
- `openclaw agents list`
- `openclaw cron list`
- `openclaw status`
- `free -h`, `df -h`, `uptime`
- `ss -tlnp`
- `/var/log/auth.log` (if readable)
- `openclaw gateway status`

Collectors must handle missing commands gracefully (not every system has openclaw).

## Keyboard Controls
- **q** — Quit
- **r** — Force refresh
- **1-5** — Focus panel
- **Tab** — Cycle panels
- **/** — Filter activity log
- **?** — Help overlay

## Refresh Rates
- Server health: 5s
- Agent/cron: 30s
- Security: 60s
- Activity log: 10s

## Theme
- Dark terminal background
- Green=healthy, Yellow=warning, Red=error, Cyan=info
- Header: bold, with UTC and local time

## Cucumber Test Scenarios

### agents.feature
```gherkin
Feature: Agent Fleet Display
  As an OpenClaw operator
  I want to see all my agents and their status
  So I can monitor fleet health

  Scenario: Display all configured agents
    Given the OpenClaw instance has 3 agents configured
    When the CIC dashboard loads the agent panel
    Then I should see 3 agents listed
    And each agent should show name, status, and model

  Scenario: Show session counts per agent
    Given agent "main" has 5 active sessions
    When the agent panel refreshes
    Then I should see "5" sessions for agent "main"

  Scenario: Handle openclaw command failure gracefully
    Given the openclaw CLI is not available
    When the agent panel tries to refresh
    Then I should see an error message instead of agent data
    And the dashboard should not crash
```

### server.feature
```gherkin
Feature: Server Health Display
  As an OpenClaw operator
  I want to see system resource usage
  So I can ensure the server is healthy

  Scenario: Display CPU, memory, and disk usage
    Given the server has system monitoring tools installed
    When the server panel refreshes
    Then I should see CPU usage as a percentage
    And I should see memory usage with used/total
    And I should see disk usage with used/total

  Scenario: Color code based on thresholds
    Given memory usage is above 90%
    When the server panel renders
    Then memory should be displayed in red

  Scenario: Show gateway status
    Given the OpenClaw gateway is running
    When the server panel refreshes
    Then I should see gateway status as "running"
```

### cron.feature
```gherkin
Feature: Cron Job Display
  As an OpenClaw operator
  I want to see cron job status
  So I can catch failures quickly

  Scenario: Display all cron jobs with status
    Given there are 5 cron jobs configured
    When the cron panel loads
    Then I should see 5 cron jobs listed
    And each should show status icon, name, and timing

  Scenario: Highlight error jobs
    Given cron job "Deal Flow Scanner" has status "error"
    When the cron panel renders
    Then "Deal Flow Scanner" should be displayed in red
    And it should show the error icon

  Scenario: Show consecutive error count
    Given a cron job has 12 consecutive errors
    When the cron panel renders
    Then I should see the error count "12"
```

### security.feature
```gherkin
Feature: Security Status Display
  As an OpenClaw operator
  I want to see security posture at a glance
  So I can identify threats quickly

  Scenario: Show SSH login status
    Given there were 0 failed SSH logins in the last 24h
    When the security panel refreshes
    Then SSH status should show green with "No intrusions"

  Scenario: Alert on high failed login count
    Given there were 500 failed SSH logins in the last 24h
    When the security panel refreshes
    Then SSH status should show red with the count

  Scenario: Show listening ports
    Given there are 4 listening ports
    When the security panel refreshes
    Then I should see "4 listening" ports
```

### navigation.feature
```gherkin
Feature: Keyboard Navigation
  As a user
  I want to navigate the dashboard with keyboard
  So I can interact without a mouse

  Scenario: Quit with q
    Given the dashboard is running
    When I press "q"
    Then the dashboard should exit

  Scenario: Force refresh with r
    Given the dashboard is running
    When I press "r"
    Then all panels should refresh immediately

  Scenario: Focus panel with number keys
    Given the dashboard is running
    When I press "1"
    Then the agent panel should be focused/expanded
```

## GitHub Actions CI

### ci.yml
- Trigger: push to main, PRs
- Matrix: Python 3.10, 3.11, 3.12
- Steps: install deps, lint (flake8/ruff), run behave tests, run unit tests
- Badge in README

### release.yml
- Trigger: tag v*
- Build sdist and wheel
- Create GitHub release with artifacts

## README.md Requirements
- Project banner/description
- CI badge (linked to Actions)
- Install instructions (pip, OpenClaw skill, manual)
- Screenshot/demo section
- Usage section
- Link to TESTS.md
- Contributing section
- License

## TESTS.md Requirements
- Table of all test scenarios with:
  - Feature file
  - Scenario name
  - Status (✅ passing / ❌ failing / ⏳ pending)
  - Last updated date
- Link back to README
- Instructions to run tests locally
