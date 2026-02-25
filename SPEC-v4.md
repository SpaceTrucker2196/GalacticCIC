# GalacticCIC v4 — Responsiveness & Theme System

## 1. Fix Server Panel Not Updating
The server health panel doesn't seem to update. Debug:
- Verify `_refresh_all_data()` actually calls `get_server_health()` and updates panel[1]
- Make sure sparkline history arrays grow with each refresh (append new values)
- The DB recording must happen BEFORE querying historical data
- Print/log to verify data flows through

## 2. NMAP Activity Indicator
In the security panel, show `[NMAP]` in YELLOW when nmap scans are actively running:
- Add a shared flag: `self._nmap_active = False` on the app
- Set to True before starting nmap scans in `_refresh_all_data()`
- Set to False when nmap scans complete
- Pass this flag to the security panel for display
- Security panel title: `Security Status [NMAP]` (yellow) when active

## 3. Set Refresh Rate to 5 Seconds
Change `REFRESH_INTERVAL = 5` (from 30).
The background thread approach means this won't block the UI even at 5s.

## 4. Sparklines Must Update Every Refresh
- Each refresh should append new data point to sparkline history
- Keep last 60 data points (5s * 60 = 5 minutes of history) 
- The sparkline rendering must use the LATEST data from the arrays
- Verify the sparkline chars actually change when values change

## 5. Process List on Server Panel
Add top processes by CPU/memory to the bottom of the server health panel:
- Collect via: `ps aux --sort=-%cpu | head -6` (top 5 + header)
- Parse: PID, USER, %CPU, %MEM, COMMAND
- Display in Table format below the sparklines:
```
  Top Processes:
  PID    CPU%  MEM%  CMD
  51818  12.3   4.1  openclaw-gateway
  809912  8.7   2.3  claude
  154122  3.2   1.8  openclaw-tui
```
- Add `get_top_processes()` collector function

## 6. Theme System
Create `src/galactic_cic/theme.py`:

```python
class Theme:
    """GalacticCIC theme definition."""
    def __init__(self, name, colors):
        self.name = name
        self.colors = colors  # dict mapping role -> (fg, bg) curses color constants
    
THEMES = {
    "phosphor": Theme("phosphor", {
        "normal":    (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "highlight": (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "warning":   (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "error":     (curses.COLOR_RED, curses.COLOR_BLACK),
        "dim":       (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "header":    (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "footer":    (curses.COLOR_GREEN, curses.COLOR_BLACK),
        "nmap":      (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    }),
    "amber": Theme("amber", {
        "normal":    (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "highlight": (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "warning":   (curses.COLOR_RED, curses.COLOR_BLACK),
        "error":     (curses.COLOR_RED, curses.COLOR_BLACK),
        "dim":       (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "header":    (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "footer":    (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "nmap":      (curses.COLOR_RED, curses.COLOR_BLACK),
    }),
    "blue": Theme("blue", {
        "normal":    (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "highlight": (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "warning":   (curses.COLOR_YELLOW, curses.COLOR_BLACK),
        "error":     (curses.COLOR_RED, curses.COLOR_BLACK),
        "dim":       (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "header":    (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "footer":    (curses.COLOR_CYAN, curses.COLOR_BLACK),
        "nmap":      (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    }),
}

DEFAULT_THEME = "phosphor"
```

### Theme Integration:
- Load theme name from `~/.galactic_cic/config.json` (create if missing):
  ```json
  {"theme": "phosphor"}
  ```
- Add keybinding `t` to cycle themes at runtime
- `_init_colors()` reads from current theme
- Theme change takes effect immediately (re-init color pairs)

### Config file: `~/.galactic_cic/config.json`
```json
{
    "theme": "phosphor",
    "refresh_interval": 5
}
```

## Implementation Notes
- The curses COLOR constants are not available until curses is initialized
- Theme must be a data structure that can be evaluated after curses.initscr()
- Use string constants for colors in theme definition, map to curses constants at init time
- All network/subprocess calls MUST stay in the background thread
- Keep all 25 scenarios / 83 steps passing
