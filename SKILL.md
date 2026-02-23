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

# GalacticCIC — Claw Information Center

An htop-style interactive terminal dashboard for OpenClaw operations monitoring.

## Quick Start

```bash
python3 -m galactic_cic
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| q | Quit |
| r | Force refresh all panels |
| 1-5 | Focus specific panel |
| Tab | Cycle panels |
| / | Filter activity log |
| ? | Help overlay |
| Esc | Close dialogs / clear filter |
