# Network & Security Panel Enhancements

## 1. Nmap Scan on Heartbeat
- Run `nmap -sT localhost` on every data refresh cycle (security refresh = 60s)
- Store scan results in SQLite `port_scans` table
- Display in security panel with last scan timestamp

## 2. Network Activity Graph in Server Health Panel
- Add an ASCII network activity graph showing connections over time
- Use `ss -tnp` to count active connections per refresh
- Store in new `network_metrics` table:
  ```sql
  CREATE TABLE IF NOT EXISTS network_metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp REAL NOT NULL,
      active_connections INTEGER DEFAULT 0,
      unique_ips INTEGER DEFAULT 0
  );
  ```
- Draw a simple ASCII sparkline/bar graph of connections over last hour
- Example: `Net: ▁▂▃▂▅▃▂▁▃▂ 8 conn`

## 3. Top 3 Connected IPs with DNS Resolution
- Parse `ss -tnp` output to extract unique peer IPs
- Resolve each IP with `host <ip>` or `dig -x <ip> +short` (async, cached)
- Show top 3 by connection count in server health panel:
  ```
  Top IPs:
    174.224.243.131  3  spacetrucker (home)
    104.248.168.210  1  digitalocean.com
    64.23.226.72     1  unknown
  ```
- Cache DNS resolutions in DB to avoid repeated lookups:
  ```sql
  CREATE TABLE IF NOT EXISTS dns_cache (
      ip TEXT PRIMARY KEY,
      hostname TEXT DEFAULT '',
      resolved_at REAL NOT NULL
  );
  ```

## 4. SSH Login Summary in Security Panel
- Parse `/var/log/auth.log` for recent Accepted/Failed SSH logins
- Show top 3 IPs for both successful and failed logins with:
  - IP address
  - Connection count
  - DNS-resolved hostname (from cache)
  - Last seen timestamp
- Example in security panel:
  ```
  SSH Logins (24h):
    174.224.243.131  12  home-isp.net     2h ago
    96.42.52.151      3  mobile.net       8h ago
  SSH Failed (24h):
    104.248.168.210  47  bad-actor.com    1h ago
    45.33.32.156     12  scanner.net      3h ago
  ```

## 5. DB Schema Additions
Add to database.py schema:
```sql
CREATE TABLE IF NOT EXISTS network_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    active_connections INTEGER DEFAULT 0,
    unique_ips INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dns_cache (
    ip TEXT PRIMARY KEY,
    hostname TEXT DEFAULT '',
    resolved_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_network_ts ON network_metrics(timestamp);
```

## 6. Collector Updates

### collectors.py additions:
- `get_network_activity()` — parse `ss -tnp`, count connections, extract IPs
- `get_top_ips(limit=3)` — top connected IPs with DNS resolution
- `get_ssh_login_summary()` — parse auth.log for accepted/failed with IP counts
- `resolve_ip(ip)` — async DNS resolution with DB caching (cache 24h)
- Update `get_security_status()` — include nmap results, SSH login summary

## 7. Panel Updates

### Server Health Panel:
- Add network graph (ASCII sparkline) after disk usage
- Show top 3 connected IPs below the graph

### Security Panel:
- Add SSH login summary (top 3 successful + top 3 failed IPs)
- Each with count, resolved hostname, last seen
- Show last nmap scan time

## Implementation Notes
- DNS resolution MUST be async (don't block UI)
- Cache DNS results in SQLite for 24 hours
- Network graph uses Unicode block characters: ▁▂▃▄▅▆▇█
- Known IPs (174.224.243.131, 96.42.52.151) are Jeff's — could label "Captain" in future
- All new data stored in DB for historical trending
- nmap scan timeout: 10 seconds max
