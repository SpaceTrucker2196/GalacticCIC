# GalacticCIC — Security Panel v2 & Activity Log Overhaul

## 1. Nmap Scan of Top 3 Failed SSH Source IPs

When failed SSH attempts are detected, nmap scan the top 3 attacker IPs:
- `nmap -sT --top-ports 20 <ip>` (timeout 10s per IP)
- Cache results in SQLite `attacker_scans` table (refresh every 6h):
  ```sql
  CREATE TABLE IF NOT EXISTS attacker_scans (
      ip TEXT PRIMARY KEY,
      open_ports TEXT DEFAULT '',
      os_guess TEXT DEFAULT '',
      scanned_at REAL NOT NULL
  );
  ```
- Display in security panel under "SSH Failed":
  ```
  SSH Failed (24h):
   45.33.32.156    47  scanner.net    DE
     ports: 22,80,443  os: Linux
   104.248.168.210 12  digitalocean   US
     ports: 22         os: Linux
  ```

## 2. IP Geolocation

Infer location from IP address using free APIs (no key needed):
- Primary: `curl -s http://ip-api.com/json/<ip>?fields=country,countryCode,city,isp`
- Fallback: `curl -s https://ipinfo.io/<ip>/json` (limited)
- Cache results in SQLite `geo_cache` table:
  ```sql
  CREATE TABLE IF NOT EXISTS geo_cache (
      ip TEXT PRIMARY KEY,
      country_code TEXT DEFAULT '',
      city TEXT DEFAULT '',
      isp TEXT DEFAULT '',
      resolved_at REAL NOT NULL
  );
  ```
- TTL: 7 days (IPs don't move often)
- Show 2-letter country code next to each IP in security panel
- Rate limit: max 1 lookup per second (ip-api.com limit is 45/min)

## 3. Security Panel Layout Update
```
┌─ Security Status ──────────────────────┐
│ SSH: No intrusions                     │
│ Ports: 4 open                          │
│    22 sshd    18789 openclaw           │
│ 18792 openclaw   53 systemd-resolve    │
│                                        │
│ SSH Logins (24h):                      │
│  174.224.243.131  3 home-isp.net   US  │
│  96.42.52.151     1 mobile.net     US  │
│                                        │
│ SSH Failed (24h):                      │
│  45.33.32.156    47 scanner.net    DE  │
│    ports: 22,80,443  os: Linux         │
│  104.248.168.210 12 digitalocean   US  │
│    ports: 22  os: Linux                │
│  91.189.42.11     8 unknown        CN  │
│    ports: 22,8080  os: Linux           │
│                                        │
│ UFW: Inactive  Fail2ban: Inactive      │
│ RootLogin: Enabled                     │
└────────────────────────────────────────┘
```

## 4. Activity Log Overhaul

The activity log panel should be split into two sections:

### Upper Section: Errors (always visible, red text)
- OpenClaw cron job errors
- Failed SSH attempts (summary, not every line)
- Any system errors from openclaw logs
- Source: `openclaw cron list` (filter status=error), system logs

### Lower Section: Recent Activity (scrolling, green text)  
- Tail the most relevant OpenClaw logs
- Source: `openclaw logs --limit 20` or `tail -20 ~/.openclaw/logs/gateway.log`
- Also include: recent SSH logins, cron completions, system events
- Format each line: `HH:MM  [source]  message`

### Layout:
```
┌─ Activity Log ─────────────────────────────────────────────┐
│ ERRORS:                                                    │
│  15:24 [cron] OpenClaw Update Check: delivery failed       │
│  14:02 [ssh]  47 failed attempts from 45.33.32.156         │
│ ──────────────────────────────────────────────────────────  │
│ RECENT:                                                    │
│  15:34 [cron] Deal Flow Scanner completed — 22 listings    │
│  15:00 [cron] CISA KEV check — mostly clear                │
│  13:00 [cron] Harvey St Checklist — ok                     │
│  12:00 [cron] Daily Agent Backup — ok                      │
│  09:44 [ssh]  Login from 174.224.243.131 (spacetrucker)    │
│  09:02 [sys]  GalacticCIC Tufte update pushed              │
└────────────────────────────────────────────────────────────┘
```

## 5. New Collector Functions

### collectors.py additions:
- `scan_attacker_ip(ip)` — nmap scan of failed SSH source IP (async, timeout 10s)
- `get_ip_geolocation(ip)` — fetch geo data from ip-api.com (async, cached 7d)
- `get_failed_ssh_details()` — parse auth.log for failed IPs with counts + last seen
- `get_openclaw_logs(limit=20)` — tail openclaw gateway/agent logs
- `get_error_summary()` — aggregate errors from cron + system logs

### All new network calls MUST:
- Be async (don't block UI)
- Have timeouts (10s for nmap, 5s for HTTP)
- Cache results in SQLite
- Handle failures gracefully (show "?" not crash)

## 6. DB Schema Additions
```sql
CREATE TABLE IF NOT EXISTS attacker_scans (
    ip TEXT PRIMARY KEY,
    open_ports TEXT DEFAULT '',
    os_guess TEXT DEFAULT '',
    scanned_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_cache (
    ip TEXT PRIMARY KEY,
    country_code TEXT DEFAULT '',
    city TEXT DEFAULT '',
    isp TEXT DEFAULT '',
    resolved_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attacker_ip ON attacker_scans(ip);
CREATE INDEX IF NOT EXISTS idx_geo_ip ON geo_cache(ip);
```

## Rules
- Standard curses colors ONLY (GREEN/RED/YELLOW)
- ALL text phosphor green unless error (red) or warning (yellow)  
- Error section in activity log uses RED
- Keep all tests passing
- Pure Python stdlib + urllib (for HTTP geo lookups)
- nmap calls via subprocess, not library
