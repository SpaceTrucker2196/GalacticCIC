"""Behave test environment setup for GalacticCIC."""

import sys
import os

# Ensure src/ is on the path so galactic_cic is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def before_all(context):
    """Set up test-wide context."""
    context.test_data = {}


def before_scenario(context, scenario):
    """Reset per-scenario state."""
    context.test_data = {}
    context.panel_output = None
    context.error = None
