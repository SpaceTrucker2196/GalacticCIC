#!/usr/bin/env bash
set -euo pipefail

echo "=== GalacticCIC Installer ==="

# Check for python3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is required but not found."
    exit 1
fi

echo "Python3 found: $(python3 --version)"

# Install dependencies
echo "Installing Python dependencies..."
pip3 install --break-system-packages -q textual rich behave 2>/dev/null \
    || pip3 install -q textual rich behave

# Install the package in dev mode
echo "Installing galactic-cic..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
pip3 install --break-system-packages -e "$SCRIPT_DIR" 2>/dev/null \
    || pip3 install -e "$SCRIPT_DIR"

# Check for openclaw (optional)
if command -v openclaw &>/dev/null; then
    echo "OpenClaw CLI found: $(openclaw --version 2>/dev/null || echo 'version unknown')"
else
    echo "NOTE: openclaw CLI not found. Dashboard will show placeholder data."
fi

echo ""
echo "Installation complete! Launch with:"
echo "  python3 -m galactic_cic"
