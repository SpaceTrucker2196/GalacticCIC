"""Trend calculations and tokens/hour from historical metrics."""

import time


# Arrow indicators
ARROW_UP = "\u2191"    # ↑
ARROW_DOWN = "\u2193"  # ↓
ARROW_STABLE = "\u2192"  # →
NO_DATA = "--"


class TrendCalculator:
    """Calculate trends and rates from historical metrics."""

    def __init__(self, db):
        self.db = db

    def _get_trend_arrow(self, current, previous):
        """Compare current to previous and return trend arrow."""
        if previous is None or current is None:
            return NO_DATA
        diff = current - previous
        # Use 5% threshold for stability
        if previous > 0:
            pct_change = abs(diff) / previous
            if pct_change < 0.05:
                return ARROW_STABLE
        elif abs(diff) < 0.5:
            return ARROW_STABLE
        if diff > 0:
            return ARROW_UP
        elif diff < 0:
            return ARROW_DOWN
        return ARROW_STABLE

    def get_server_trends(self):
        """Get trend arrows for CPU, MEM, DISK by comparing now vs 1h ago.

        Returns dict with keys: cpu_trend, mem_trend, disk_trend
        """
        now = time.time()
        one_hour_ago = now - 3600

        result = {
            "cpu_trend": NO_DATA,
            "mem_trend": NO_DATA,
            "disk_trend": NO_DATA,
        }

        # Get most recent reading
        current = self.db.fetchone(
            "SELECT cpu_percent, mem_used_mb, disk_used_gb "
            "FROM server_metrics ORDER BY timestamp DESC LIMIT 1"
        )
        if not current:
            return result

        # Get reading closest to 1 hour ago
        past = self.db.fetchone(
            "SELECT cpu_percent, mem_used_mb, disk_used_gb "
            "FROM server_metrics WHERE timestamp <= ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (one_hour_ago,),
        )
        if not past:
            return result

        result["cpu_trend"] = self._get_trend_arrow(
            current["cpu_percent"], past["cpu_percent"]
        )
        result["mem_trend"] = self._get_trend_arrow(
            current["mem_used_mb"], past["mem_used_mb"]
        )
        result["disk_trend"] = self._get_trend_arrow(
            current["disk_used_gb"], past["disk_used_gb"]
        )

        return result

    def get_agent_tokens_per_hour(self):
        """Calculate tokens/hour for each agent over the last 1 hour.

        Returns dict mapping agent_name -> tokens_per_hour (int).
        Also includes '_total' key for aggregate.
        """
        now = time.time()
        one_hour_ago = now - 3600

        result = {}

        # Get distinct agents from recent data
        agents = self.db.fetchall(
            "SELECT DISTINCT agent_name FROM agent_metrics "
            "WHERE timestamp >= ?",
            (one_hour_ago,),
        )

        total_tph = 0
        for row in agents:
            name = row["agent_name"]

            # Get earliest reading in the window
            earliest = self.db.fetchone(
                "SELECT tokens_used, timestamp FROM agent_metrics "
                "WHERE agent_name = ? AND timestamp >= ? "
                "ORDER BY timestamp ASC LIMIT 1",
                (name, one_hour_ago),
            )
            # Get latest reading
            latest = self.db.fetchone(
                "SELECT tokens_used, timestamp FROM agent_metrics "
                "WHERE agent_name = ? ORDER BY timestamp DESC LIMIT 1",
                (name,),
            )

            if earliest and latest and latest["timestamp"] > earliest["timestamp"]:
                token_diff = latest["tokens_used"] - earliest["tokens_used"]
                time_diff_hours = (
                    (latest["timestamp"] - earliest["timestamp"]) / 3600
                )
                if time_diff_hours > 0 and token_diff >= 0:
                    tph = int(token_diff / time_diff_hours)
                    result[name] = tph
                    total_tph += tph
                else:
                    result[name] = 0
            else:
                result[name] = 0

        result["_total"] = total_tph
        return result

    def get_agent_token_trends(self):
        """Get trend arrows for each agent's token usage.

        Returns dict mapping agent_name -> trend arrow.
        """
        now = time.time()
        one_hour_ago = now - 3600

        result = {}

        agents = self.db.fetchall(
            "SELECT DISTINCT agent_name FROM agent_metrics "
            "WHERE timestamp >= ?",
            (one_hour_ago,),
        )

        for row in agents:
            name = row["agent_name"]

            current = self.db.fetchone(
                "SELECT tokens_used FROM agent_metrics "
                "WHERE agent_name = ? ORDER BY timestamp DESC LIMIT 1",
                (name,),
            )
            past = self.db.fetchone(
                "SELECT tokens_used FROM agent_metrics "
                "WHERE agent_name = ? AND timestamp <= ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (name, one_hour_ago),
            )

            if current and past:
                result[name] = self._get_trend_arrow(
                    current["tokens_used"], past["tokens_used"]
                )
            else:
                result[name] = NO_DATA

        return result
