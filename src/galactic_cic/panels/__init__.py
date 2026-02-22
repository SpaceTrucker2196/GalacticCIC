"""Dashboard panels for GalacticCIC."""

from galactic_cic.panels.agents import AgentFleetPanel
from galactic_cic.panels.server import ServerHealthPanel
from galactic_cic.panels.cron import CronJobsPanel
from galactic_cic.panels.security import SecurityPanel
from galactic_cic.panels.activity import ActivityLogPanel

__all__ = [
    "AgentFleetPanel",
    "ServerHealthPanel",
    "CronJobsPanel",
    "SecurityPanel",
    "ActivityLogPanel",
]
