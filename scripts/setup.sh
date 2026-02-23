#!/bin/bash
# GalacticCIC Setup Script
# Works on any Debian/Ubuntu system with OpenClaw installed

set -e

echo "GalacticCIC Setup"
echo "===================="

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required"
    exit 1
fi

# Check Python version >= 3.10
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "Python >= 3.10 required (found $PY_VER)"
    exit 1
fi
echo "Python $PY_VER"

# Check for openclaw (warn but don't fail)
if command -v openclaw &>/dev/null; then
    OC_VER=$(openclaw --version 2>/dev/null || echo "unknown")
    echo "OpenClaw $OC_VER"
else
    echo "WARNING: OpenClaw not found -- dashboard will show limited data"
fi

# Check for nmap (optional)
if command -v nmap &>/dev/null; then
    echo "nmap available"
else
    echo "INFO: nmap not found -- port scanning will use ss instead"
fi

# Install galactic_cic
echo ""
echo "Installing GalacticCIC..."
pip install --break-system-packages -e . 2>/dev/null || pip install -e .

# Create data directory
mkdir -p ~/.galactic_cic
echo "Data directory: ~/.galactic_cic"

# Verify installation
if command -v galactic_cic &>/dev/null; then
    echo ""
    echo "GalacticCIC installed successfully!"
    echo "   Run: galactic_cic"
else
    echo ""
    echo "WARNING: galactic_cic not found in PATH"
    echo "   Try: python3 -m galactic_cic"
fi
