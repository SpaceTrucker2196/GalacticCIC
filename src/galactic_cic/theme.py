"""GalacticCIC theming system — centralized color/style definitions."""

import curses
import json
import os

# Color role constants
NORMAL = "normal"
HIGHLIGHT = "highlight"
WARNING = "warning"
ERROR = "error"
DIM = "dim"
HEADER = "header"
FOOTER = "footer"
TABLE_HEADING = "table_heading"

# Curses color pair IDs for each role
PAIR_IDS = {
    NORMAL: 1,
    HIGHLIGHT: 2,
    WARNING: 3,
    ERROR: 4,
    DIM: 5,
    HEADER: 6,
    FOOTER: 7,
    TABLE_HEADING: 8,
}

# Custom color ID for dark green background (curses supports 256 colors)
DARK_GREEN_ID = 16

# Map string names to curses color constants (resolved after curses init)
_COLOR_NAMES = {
    "green": "COLOR_GREEN",
    "yellow": "COLOR_YELLOW",
    "red": "COLOR_RED",
    "white": "COLOR_WHITE",
    "cyan": "COLOR_CYAN",
    "black": "COLOR_BLACK",
    "magenta": "COLOR_MAGENTA",
    "blue": "COLOR_BLUE",
}


class Theme:
    """Color theme definition using string color names."""

    def __init__(self, name, colors, attrs=None):
        """
        Args:
            name: Human-readable theme name.
            colors: dict of role -> (fg_name, bg_name) using string color names.
            attrs: dict of role -> list of curses attribute name strings.
        """
        self.name = name
        self.colors = colors
        self.attrs = attrs or {}


# Theme definitions — use string names so they can be defined before curses init
THEMES = {
    "phosphor": Theme("phosphor", {
        NORMAL:        ("green", "darkgreen"),
        HIGHLIGHT:     ("green", "darkgreen"),
        WARNING:       ("yellow", "darkgreen"),
        ERROR:         ("red", "darkgreen"),
        DIM:           ("green", "darkgreen"),
        HEADER:        ("green", "darkgreen"),
        FOOTER:        ("green", "darkgreen"),
        TABLE_HEADING: ("white", "darkgreen"),
    }, {
        HIGHLIGHT: ["A_BOLD"],
        HEADER: ["A_BOLD"],
        ERROR: ["A_BOLD"],
        TABLE_HEADING: ["A_DIM"],
    }),
    "amber": Theme("amber", {
        NORMAL:        ("yellow", "black"),
        HIGHLIGHT:     ("yellow", "black"),
        WARNING:       ("red", "black"),
        ERROR:         ("red", "black"),
        DIM:           ("yellow", "black"),
        HEADER:        ("yellow", "black"),
        FOOTER:        ("yellow", "black"),
        TABLE_HEADING: ("white", "black"),
    }, {
        HIGHLIGHT: ["A_BOLD"],
        HEADER: ["A_BOLD"],
        ERROR: ["A_BOLD"],
        TABLE_HEADING: ["A_DIM"],
    }),
    "blue": Theme("blue", {
        NORMAL:        ("cyan", "black"),
        HIGHLIGHT:     ("cyan", "black"),
        WARNING:       ("yellow", "black"),
        ERROR:         ("red", "black"),
        DIM:           ("cyan", "black"),
        HEADER:        ("cyan", "black"),
        FOOTER:        ("cyan", "black"),
        TABLE_HEADING: ("white", "black"),
    }, {
        HIGHLIGHT: ["A_BOLD"],
        HEADER: ["A_BOLD"],
        ERROR: ["A_BOLD"],
        TABLE_HEADING: ["A_DIM"],
    }),
}

DEFAULT_THEME = "phosphor"

# Module-level state
_current_theme_name = DEFAULT_THEME
_initialized = False


_dark_green_available = False


def _resolve_color(name):
    """Resolve a string color name to a curses constant.

    'default' or 'black' maps to -1 (terminal default background)
    when use_default_colors() has been called.
    'darkgreen' maps to our custom dark green color (ID 16) if available,
    otherwise falls back to terminal default (-1).
    """
    mapping = {
        "green": curses.COLOR_GREEN,
        "yellow": curses.COLOR_YELLOW,
        "red": curses.COLOR_RED,
        "white": curses.COLOR_WHITE,
        "cyan": curses.COLOR_CYAN,
        "black": -1,
        "default": -1,
        "darkgreen": DARK_GREEN_ID if _dark_green_available else -1,
        "magenta": curses.COLOR_MAGENTA,
        "blue": curses.COLOR_BLUE,
    }
    return mapping.get(name, curses.COLOR_WHITE)


def _resolve_attr(name):
    """Resolve a string attribute name to a curses constant."""
    mapping = {
        "A_BOLD": curses.A_BOLD,
        "A_DIM": curses.A_DIM,
        "A_UNDERLINE": curses.A_UNDERLINE,
        "A_REVERSE": curses.A_REVERSE,
        "A_BLINK": curses.A_BLINK,
        "A_NORMAL": curses.A_NORMAL,
    }
    return mapping.get(name, 0)


def get_theme(name=None):
    """Get a Theme by name (or current theme)."""
    if name is None:
        name = _current_theme_name
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def get_current_theme_name():
    """Return the name of the currently active theme."""
    return _current_theme_name


def set_theme(name):
    """Set the current theme name. Call init_colors() after to apply."""
    global _current_theme_name
    if name in THEMES:
        _current_theme_name = name
        return True
    return False


def cycle_theme():
    """Cycle to the next theme. Returns new theme name."""
    names = list(THEMES.keys())
    idx = names.index(_current_theme_name) if _current_theme_name in names else 0
    new_name = names[(idx + 1) % len(names)]
    set_theme(new_name)
    return new_name


def init_colors(theme_name=None):
    """Initialize curses color pairs from theme. Call after curses.initscr()."""
    global _initialized
    if theme_name:
        set_theme(theme_name)

    curses.start_color()
    curses.use_default_colors()

    # Define dark green background color if terminal supports custom colors
    global _dark_green_available
    _dark_green_available = False
    try:
        if curses.can_change_color() and curses.COLORS > DARK_GREEN_ID:
            curses.init_color(DARK_GREEN_ID, 40, 100, 40)
            _dark_green_available = True
    except (curses.error, ValueError):
        pass  # Terminal doesn't support custom colors

    theme = get_theme()
    for role, pair_id in PAIR_IDS.items():
        fg_name, bg_name = theme.colors.get(role, ("green", "black"))
        curses.init_pair(pair_id, _resolve_color(fg_name), _resolve_color(bg_name))

    _initialized = True


def get_attr(role):
    """Get the curses attribute (color pair + flags) for a color role.

    Call after init_colors().
    """
    if not _initialized:
        return 0

    pair_id = PAIR_IDS.get(role, PAIR_IDS[NORMAL])
    attr = curses.color_pair(pair_id)

    theme = get_theme()
    for attr_name in theme.attrs.get(role, []):
        attr |= _resolve_attr(attr_name)

    return attr


def get_pair_id(role):
    """Get the raw curses color pair ID for a role."""
    return PAIR_IDS.get(role, PAIR_IDS[NORMAL])


def load_config():
    """Load theme name from ~/.galactic_cic/config.json."""
    config_path = os.path.expanduser("~/.galactic_cic/config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
        name = config.get("theme", DEFAULT_THEME)
        if name in THEMES:
            set_theme(name)
            return name
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return DEFAULT_THEME


def save_config():
    """Save current theme to ~/.galactic_cic/config.json."""
    config_dir = os.path.expanduser("~/.galactic_cic")
    config_path = os.path.join(config_dir, "config.json")
    try:
        os.makedirs(config_dir, exist_ok=True)
        config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
        config["theme"] = _current_theme_name
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except (OSError, json.JSONDecodeError):
        pass
