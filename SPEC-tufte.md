# GalacticCIC — Tufte Sparkline & Table Reformat

## Problem
1. Agents disappeared from agent panel (drawing issue — data is fine)
2. Panels need consistent table-based layout for readability
3. Need Edward Tufte-style sparklines for CPU, storage, network with historical averages

## Tufte Sparklines
Edward Tufte's sparklines are "intense, simple, word-sized graphics." They show:
- A time series using Unicode block chars: ▁▂▃▄▅▆▇█
- The current value highlighted (or shown at end)
- A reference line showing the historical average (using ─ or showing avg number)
- Min/max markers if space allows

### Sparkline Format
```
CPU:  ▁▂▃▂▅▃▂▁▃▂▅▇▅▃▂▁▃▅  23%  avg:18%
MEM:  ▅▅▅▆▅▅▆▅▅▅▅▆▅▅▅▅▅▅  58%  avg:55%
DISK: ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇   3%  avg:3%
NET:  ▁▁▂▁▃▁▁▂▅▂▁▁▂▁▃▂▁▂   8   avg:4
```

### Implementation
- Pull historical data from SQLite `server_metrics` and `network_metrics` tables
- Use last 20 data points for sparkline (or fewer if not enough data yet)
- Calculate average from ALL historical data (last 24h)
- Show current value + average after the sparkline
- Use the existing `_make_sparkline()` method but enhance it

## Panel Layouts (All Using Tables)

### Agent Fleet Panel
```
┌─ Agent Fleet ──────────────────────────┐
│ Agent       Model       Stor  Tok  T/h │
│ ─────────────────────────────────────  │
│ main*       opus-4-6     28M  242k 42k │
│ rentalops   opus-4-6    274M   60k 12k │
│ raven       opus-4-6    192K    0k  -- │
│                                        │
│ Sessions: 10  Gateway: running         │
│ v2026.2.21-2                           │
└────────────────────────────────────────┘
```
- Use Table class with borders=False
- Mark default agent with *
- CRITICAL: The _draw_content method must call table.draw() and actually render

### Server Health Panel  
```
┌─ Server Health ────────────────────────┐
│ CPU:  ▁▂▃▂▅▃▂▁▃▂▅▇▅▃  23%  avg:18%   │
│ MEM:  ▅▅▅▆▅▅▆▅▅▅▅▆▅▅  58%  avg:55%   │
│ DISK: ▇▇▇▇▇▇▇▇▇▇▇▇▇▇   3%  avg:3%   │
│ NET:  ▁▁▂▁▃▁▁▂▅▂▁▁▂▁   8   avg:4     │
│                                        │
│ LOAD: 0.42 0.38 0.31   UP: 2d 14h     │
│                                        │
│ Top IPs:                               │
│  174.224.243.131   3  home-isp.net     │
│  104.248.168.210   1  digitalocean     │
│  64.23.226.72      1  unknown          │
└────────────────────────────────────────┘
```
- Sparklines for CPU, MEM, DISK, NET
- Each shows: sparkline + current value + historical average
- Top IPs in table below

### Cron Jobs Panel
```
┌─ Cron Jobs ────────────────────────────┐
│   Job                Last     Next     │
│ ─────────────────────────────────────  │
│ ✓ Deal Flow Scanner  2h ago   in 4h   │
│ ✓ Daily Backup       1h ago   in 23h  │
│ ✓ Harvey St Check    <1m      in 24h  │
│ ✗ Update Check       21h ago  in 6d   │
│ ◌ CISA KEV           --       in 2h   │
│ ✓ Security Audit     5h ago   in 7h   │
│ ✓ Weather Report     18h ago  in 6h   │
└────────────────────────────────────────┘
```

### Security Panel
```
┌─ Security Status ──────────────────────┐
│ SSH:  No intrusions                    │
│ Ports: 4 open                          │
│   Port  Service                        │
│     22  sshd                           │
│  18789  openclaw                       │
│  18792  openclaw                       │
│     53  systemd-resolve                │
│                                        │
│ SSH Logins (24h):                      │
│  174.224.243.131   3  isp.net    2h    │
│  96.42.52.151      1  mobile     8h    │
│ SSH Failed (24h):                      │
│  (none)                                │
│                                        │
│ UFW: Inactive  Fail2ban: Inactive      │
│ RootLogin: Enabled                     │
└────────────────────────────────────────┘
```

## Getting Historical Data for Sparklines

### From database.py MetricsDB:
```python
def get_recent_server_metrics(self, hours=1, limit=20):
    """Get recent server metrics for sparklines."""
    cutoff = time.time() - (hours * 3600)
    return self.conn.execute(
        "SELECT cpu_percent, mem_used_mb, mem_total_mb, disk_used_gb, disk_total_gb "
        "FROM server_metrics WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?",
        (cutoff, limit)
    ).fetchall()

def get_server_averages(self, hours=24):
    """Get 24h averages for reference lines."""
    cutoff = time.time() - (hours * 3600)
    return self.conn.execute(
        "SELECT AVG(cpu_percent), AVG(mem_used_mb * 100.0 / NULLIF(mem_total_mb, 0)), "
        "AVG(disk_used_gb * 100.0 / NULLIF(disk_total_gb, 0)) "
        "FROM server_metrics WHERE timestamp > ?",
        (cutoff,)
    ).fetchone()

def get_recent_network_metrics(self, hours=1, limit=20):
    cutoff = time.time() - (hours * 3600)
    return self.conn.execute(
        "SELECT active_connections FROM network_metrics "
        "WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?",
        (cutoff, limit)
    ).fetchall()

def get_network_average(self, hours=24):
    cutoff = time.time() - (hours * 3600)
    row = self.conn.execute(
        "SELECT AVG(active_connections) FROM network_metrics WHERE timestamp > ?",
        (cutoff,)
    ).fetchone()
    return row[0] if row and row[0] else 0
```

### Feed into panels via app.py refresh cycle

## Key Rules
1. Standard curses colors ONLY (COLOR_GREEN, COLOR_RED, COLOR_YELLOW)
2. ALL text phosphor green unless error/warning
3. Keep existing tests passing
4. Agent data IS present (verified) — fix the drawing bug
5. Tables for everything structured
6. Sparklines with historical averages from SQLite
