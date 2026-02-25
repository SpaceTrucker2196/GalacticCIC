"""Tests for theme system, panel rendering, and grey table headings.

All tests use mock/fake data -- no real server, no curses terminal needed.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# We need to mock curses BEFORE importing theme/panels, since they import curses
# at function call time. We patch the curses module functions used by theme.

import curses as _real_curses

from galactic_cic.panels.base import StyledText, Table
from galactic_cic import theme
from galactic_cic.panels.cron import CronJobsPanel
from galactic_cic.panels.server import ServerHealthPanel
from galactic_cic.panels.agents import AgentFleetPanel
from galactic_cic.panels.security import SecurityPanel
from galactic_cic.panels.activity import ActivityLogPanel


# Storage for fake color pairs
_fake_pairs = {}


def _fake_start_color():
    pass


def _fake_use_default_colors():
    pass


def _fake_init_pair(pair_id, fg, bg):
    _fake_pairs[pair_id] = (fg, bg)


def _fake_color_pair(pair_id):
    return pair_id << 8


def _fake_can_change_color():
    return True


def _fake_init_color(color_id, r, g, b):
    pass


def _init_theme_for_test():
    """Initialize theme with mocked curses calls."""
    _fake_pairs.clear()
    theme._initialized = False
    theme._dark_green_available = False
    theme._current_theme_name = theme.DEFAULT_THEME
    import curses as _c
    _orig_colors = getattr(_c, 'COLORS', 8)
    _c.COLORS = 256
    with patch("curses.start_color", _fake_start_color), \
         patch("curses.use_default_colors", _fake_use_default_colors), \
         patch("curses.init_pair", _fake_init_pair), \
         patch("curses.color_pair", _fake_color_pair), \
         patch("curses.can_change_color", _fake_can_change_color), \
         patch("curses.init_color", _fake_init_color):
        theme.init_colors("phosphor")
    _c.COLORS = _orig_colors


def _get_attr_mocked(role):
    """Get theme attr with mocked curses.color_pair."""
    with patch("curses.color_pair", _fake_color_pair):
        return theme.get_attr(role)


# ---------------------------------------------------------------------------
# Theme tests
# ---------------------------------------------------------------------------

class TestThemeDefinitions(unittest.TestCase):
    """Test theme data structures and lookups."""

    def test_all_themes_exist(self):
        self.assertIn("phosphor", theme.THEMES)
        self.assertIn("amber", theme.THEMES)
        self.assertIn("blue", theme.THEMES)

    def test_theme_has_all_roles(self):
        required_roles = [
            theme.NORMAL, theme.HIGHLIGHT, theme.WARNING, theme.ERROR,
            theme.DIM, theme.HEADER, theme.FOOTER, theme.TABLE_HEADING,
        ]
        for name, t in theme.THEMES.items():
            for role in required_roles:
                self.assertIn(role, t.colors,
                              f"Theme '{name}' missing role '{role}'")

    def test_table_heading_is_white(self):
        for name, t in theme.THEMES.items():
            fg, bg = t.colors[theme.TABLE_HEADING]
            self.assertEqual(fg, "white",
                             f"Theme '{name}' table_heading fg should be white")

    def test_default_theme_is_phosphor(self):
        self.assertEqual(theme.DEFAULT_THEME, "phosphor")


class TestThemeInit(unittest.TestCase):
    """Test theme initialization and color pair registration."""

    def setUp(self):
        _fake_pairs.clear()
        theme._initialized = False
        theme._current_theme_name = theme.DEFAULT_THEME

    def test_init_registers_all_pairs(self):
        _init_theme_for_test()
        for role, pair_id in theme.PAIR_IDS.items():
            self.assertIn(pair_id, _fake_pairs,
                          f"Pair {pair_id} for role '{role}' not registered")

    def test_init_sets_initialized_flag(self):
        self.assertFalse(theme._initialized)
        _init_theme_for_test()
        self.assertTrue(theme._initialized)

    def test_phosphor_normal_is_green(self):
        _init_theme_for_test()
        pair = _fake_pairs[theme.PAIR_IDS[theme.NORMAL]]
        self.assertEqual(pair, (_real_curses.COLOR_GREEN, theme.DARK_GREEN_ID))

    def test_amber_normal_is_yellow(self):
        _fake_pairs.clear()
        theme._initialized = False
        with patch("curses.start_color", _fake_start_color), \
             patch("curses.use_default_colors", _fake_use_default_colors), \
             patch("curses.init_pair", _fake_init_pair):
            theme.init_colors("amber")
        pair = _fake_pairs[theme.PAIR_IDS[theme.NORMAL]]
        self.assertEqual(pair, (_real_curses.COLOR_YELLOW, -1))

    def test_blue_normal_is_cyan(self):
        _fake_pairs.clear()
        theme._initialized = False
        with patch("curses.start_color", _fake_start_color), \
             patch("curses.use_default_colors", _fake_use_default_colors), \
             patch("curses.init_pair", _fake_init_pair):
            theme.init_colors("blue")
        pair = _fake_pairs[theme.PAIR_IDS[theme.NORMAL]]
        self.assertEqual(pair, (_real_curses.COLOR_CYAN, -1))

    def test_table_heading_pair_is_white(self):
        _init_theme_for_test()
        pair = _fake_pairs[theme.PAIR_IDS[theme.TABLE_HEADING]]
        self.assertEqual(pair, (_real_curses.COLOR_WHITE, theme.DARK_GREEN_ID))


class TestThemeSwitching(unittest.TestCase):
    """Test runtime theme switching."""

    def setUp(self):
        theme._current_theme_name = theme.DEFAULT_THEME

    def test_set_theme(self):
        theme.set_theme("amber")
        self.assertEqual(theme.get_current_theme_name(), "amber")

    def test_set_invalid_theme_returns_false(self):
        result = theme.set_theme("nonexistent")
        self.assertFalse(result)
        self.assertEqual(theme.get_current_theme_name(), "phosphor")

    def test_cycle_theme(self):
        theme.set_theme("phosphor")
        names = list(theme.THEMES.keys())
        new_name = theme.cycle_theme()
        idx = names.index("phosphor")
        expected = names[(idx + 1) % len(names)]
        self.assertEqual(new_name, expected)

    def test_cycle_wraps_around(self):
        names = list(theme.THEMES.keys())
        theme.set_theme(names[0])
        for _ in range(len(names)):
            theme.cycle_theme()
        self.assertEqual(theme.get_current_theme_name(), names[0])


class TestGetAttr(unittest.TestCase):
    """Test get_attr returns correct attributes."""

    def setUp(self):
        _init_theme_for_test()

    def test_get_attr_returns_nonzero_after_init(self):
        attr = _get_attr_mocked(theme.NORMAL)
        self.assertNotEqual(attr, 0)

    def test_get_attr_returns_zero_before_init(self):
        theme._initialized = False
        attr = theme.get_attr(theme.NORMAL)
        self.assertEqual(attr, 0)
        # Restore
        theme._initialized = True

    def test_highlight_has_bold(self):
        attr = _get_attr_mocked(theme.HIGHLIGHT)
        self.assertTrue(attr & _real_curses.A_BOLD)

    def test_table_heading_has_dim(self):
        attr = _get_attr_mocked(theme.TABLE_HEADING)
        self.assertTrue(attr & _real_curses.A_DIM)

    def test_error_has_bold(self):
        attr = _get_attr_mocked(theme.ERROR)
        self.assertTrue(attr & _real_curses.A_BOLD)


class TestThemeConfig(unittest.TestCase):
    """Test theme config loading/saving."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmpdir, ".galactic_cic")
        self.config_path = os.path.join(self.config_dir, "config.json")
        theme._current_theme_name = theme.DEFAULT_THEME

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.unlink(self.config_path)
        if os.path.exists(self.config_dir):
            os.rmdir(self.config_dir)
        os.rmdir(self.tmpdir)

    def test_load_missing_config_returns_default(self):
        with patch("os.path.expanduser",
                   return_value=os.path.join(self.tmpdir, "nope", "config.json")):
            result = theme.load_config()
        self.assertEqual(result, theme.DEFAULT_THEME)

    def test_load_valid_config(self):
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump({"theme": "amber"}, f)
        with patch("os.path.expanduser", return_value=self.config_path):
            result = theme.load_config()
        self.assertEqual(result, "amber")

    def test_load_invalid_theme_name_returns_default(self):
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump({"theme": "nonexistent"}, f)
        with patch("os.path.expanduser", return_value=self.config_path):
            result = theme.load_config()
        self.assertEqual(result, theme.DEFAULT_THEME)


# ---------------------------------------------------------------------------
# Table heading style tests (render path only — no curses needed)
# ---------------------------------------------------------------------------

class TestTableHeadingStyle(unittest.TestCase):
    """Test that Table.render() uses table_heading style for headers."""

    def test_table_header_uses_table_heading_style(self):
        table = Table(
            columns=["Name", "Status"],
            widths=[10, 10],
            borders=False,
            padding=0,
            header=True,
        )
        table.add_row(["test", "ok"])
        st = table.render()
        header_spans = [s for s in st._spans if s.style == "table_heading"]
        self.assertTrue(len(header_spans) >= 1,
                        "Header should have table_heading style spans")

    def test_table_without_header_has_no_heading_style(self):
        table = Table(
            columns=["Name", "Status"],
            widths=[10, 10],
            borders=False,
            padding=0,
            header=False,
        )
        table.add_row(["test", "ok"])
        st = table.render()
        header_spans = [s for s in st._spans if s.style == "table_heading"]
        self.assertEqual(len(header_spans), 0)

    def test_data_rows_keep_their_style(self):
        table = Table(
            columns=["Name", "Status"],
            widths=[10, 10],
            borders=False,
            padding=0,
            header=True,
        )
        table.add_row(["good", "ok"], style="green")
        table.add_row(["bad", "fail"], style="red")
        st = table.render()
        green_spans = [s for s in st._spans if s.style == "green"]
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertTrue(len(green_spans) >= 1)
        self.assertTrue(len(red_spans) >= 1)

    def test_header_text_in_table_heading_spans(self):
        table = Table(
            columns=["PID", "COMMAND"],
            widths=[6, 12],
            borders=False,
            padding=0,
            header=True,
        )
        table.add_row(["123", "bash"])
        st = table.render()
        heading_text = ""
        for s in st._spans:
            if s.style == "table_heading":
                heading_text += st.plain[s.start:s.end]
        self.assertIn("PID", heading_text)
        self.assertIn("COMMAND", heading_text)


# ---------------------------------------------------------------------------
# Cron panel tests
# ---------------------------------------------------------------------------

class TestCronPanel(unittest.TestCase):
    """Test CronJobsPanel with mock data."""

    def setUp(self):
        self.panel = CronJobsPanel()

    def test_empty_job_list(self):
        data = {"jobs": [], "error": None}
        st = self.panel._build_content(data)
        self.assertIn("No cron jobs found", st.plain)

    def test_empty_with_error_message(self):
        data = {"jobs": [], "error": "openclaw not found"}
        st = self.panel._build_content(data)
        self.assertIn("No cron jobs found", st.plain)
        self.assertIn("openclaw not found", st.plain)
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertTrue(len(red_spans) >= 1)

    def test_all_jobs_ok(self):
        data = {"jobs": [
            {"name": "backup", "status": "ok", "last_run": "02:00:01",
             "next_run": "02:00:00"},
            {"name": "cleanup", "status": "ok", "last_run": "06:00:00",
             "next_run": "06:00:00"},
            {"name": "sync", "status": "ok", "last_run": "12:00:00",
             "next_run": "12:00:00"},
        ]}
        st = self.panel._build_content(data)
        self.assertIn("backup", st.plain)
        self.assertIn("cleanup", st.plain)
        self.assertIn("sync", st.plain)
        self.assertIn("\u2713", st.plain)  # ok icon
        # No red spans for ok jobs
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertEqual(len(red_spans), 0)

    def test_some_jobs_errored(self):
        data = {"jobs": [
            {"name": "backup", "status": "ok", "last_run": "02:00:01",
             "next_run": "02:00:00"},
            {"name": "deploy", "status": "error", "last_run": "03:15:00",
             "next_run": "04:00:00", "error_count": 12},
        ]}
        st = self.panel._build_content(data)
        self.assertIn("backup", st.plain)
        self.assertIn("deploy", st.plain)
        self.assertIn("12err", st.plain)
        self.assertIn("\u2717", st.plain)  # error icon
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertTrue(len(red_spans) >= 1)

    def test_error_count_shows_inline(self):
        data = {"jobs": [
            {"name": "failing-job", "status": "error",
             "last_run": "01:00:00", "next_run": "02:00:00",
             "error_count": 5},
        ]}
        st = self.panel._build_content(data)
        lines = st.plain.split("\n")
        job_lines = [l for l in lines if "failing" in l]
        self.assertTrue(len(job_lines) >= 1)
        self.assertIn("5err", job_lines[0])

    def test_jobs_with_long_names(self):
        data = {"jobs": [
            {"name": "very-long-cron-job-name-that-exceeds", "status": "ok",
             "last_run": "02:00:01", "next_run": "02:00:00"},
            {"name": "another-extremely-long-name", "status": "error",
             "last_run": "03:00:00", "next_run": "04:00:00",
             "error_count": 3},
        ]}
        st = self.panel._build_content(data)
        self.assertIsNotNone(st.plain)
        self.assertTrue(len(st.plain) > 0)
        # Error count should still appear
        self.assertIn("3err", st.plain)

    def test_error_summary_line(self):
        data = {"jobs": [
            {"name": "job1", "status": "error", "last_run": "01:00",
             "next_run": "02:00", "error_count": 5},
            {"name": "job2", "status": "error", "last_run": "01:00",
             "next_run": "02:00", "error_count": 3},
        ]}
        st = self.panel._build_content(data)
        self.assertIn("2 job(s) with 8 error(s)", st.plain)

    def test_table_heading_is_grey(self):
        data = {"jobs": [
            {"name": "backup", "status": "ok", "last_run": "02:00",
             "next_run": "03:00"},
        ]}
        st = self.panel._build_content(data)
        heading_spans = [s for s in st._spans if s.style == "table_heading"]
        self.assertTrue(len(heading_spans) >= 1,
                        "Table headers should use table_heading style")

    def test_preserved_row_styles(self):
        data = {"jobs": [
            {"name": "good", "status": "ok", "last_run": "02:00",
             "next_run": "03:00"},
            {"name": "bad", "status": "error", "last_run": "02:00",
             "next_run": "03:00", "error_count": 1},
        ]}
        st = self.panel._build_content(data)
        green_spans = [s for s in st._spans if s.style == "green"]
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertTrue(len(green_spans) >= 1, "OK rows should be green")
        self.assertTrue(len(red_spans) >= 1, "Error rows should be red")

    def test_idle_and_running_status(self):
        data = {"jobs": [
            {"name": "waiting", "status": "idle", "last_run": "--",
             "next_run": "04:00:00"},
            {"name": "active", "status": "running", "last_run": "03:00",
             "next_run": "--"},
        ]}
        st = self.panel._build_content(data)
        self.assertIn("\u25cc", st.plain)  # idle icon
        self.assertIn("\u21bb", st.plain)  # running icon


# ---------------------------------------------------------------------------
# Server panel tests
# ---------------------------------------------------------------------------

MOCK_HEALTH = {
    "cpu_percent": 23.5,
    "mem_percent": 58.2,
    "mem_used": "3.2G",
    "mem_total": "5.5G",
    "disk_percent": 82.0,
    "disk_used": "32G",
    "disk_total": "40G",
    "load_avg": [0.42, 0.38, 0.31],
    "uptime": "14d",
}

MOCK_PROCESSES = [
    {"pid": "51818", "user": "claw", "cpu": "12.3", "mem": "4.1",
     "command": "openclaw-gateway"},
    {"pid": "809912", "user": "claw", "cpu": "8.7", "mem": "2.3",
     "command": "claude"},
    {"pid": "154122", "user": "claw", "cpu": "3.2", "mem": "1.8",
     "command": "openclaw-tui"},
    {"pid": "1234", "user": "root", "cpu": "1.1", "mem": "0.5",
     "command": "sshd"},
    {"pid": "5678", "user": "root", "cpu": "0.5", "mem": "0.2",
     "command": "systemd"},
]


class TestServerPanel(unittest.TestCase):
    """Test ServerHealthPanel with mock data."""

    def setUp(self):
        self.panel = ServerHealthPanel()

    def test_basic_health_display(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("CPU:", st.plain)
        self.assertIn("MEM:", st.plain)
        self.assertIn("DISK:", st.plain)
        self.assertIn("NET:", st.plain)
        self.assertIn("LOAD:", st.plain)
        self.assertIn("UP:", st.plain)

    def test_cpu_percentage_displayed(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("24%", st.plain)  # 23.5 rounds to 24

    def test_memory_info_displayed(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("3.2G/5.5G", st.plain)

    def test_disk_info_displayed(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("32G/40G", st.plain)

    def test_load_average_displayed(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("0.42", st.plain)

    def test_uptime_displayed(self):
        self.panel.update(MOCK_HEALTH)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("14d", st.plain)


class TestServerPanelProcesses(unittest.TestCase):
    """Test process list in server panel."""

    def setUp(self):
        self.panel = ServerHealthPanel()

    def test_process_table_rendered(self):
        self.panel.update(MOCK_HEALTH, processes=MOCK_PROCESSES)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("Top Processes:", st.plain)
        self.assertIn("51818", st.plain)
        self.assertIn("openclaw-gateway", st.plain)
        self.assertIn("claude", st.plain)

    def test_process_table_columns(self):
        self.panel.update(MOCK_HEALTH, processes=MOCK_PROCESSES)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("PID", st.plain)
        self.assertIn("USER", st.plain)
        self.assertIn("CPU%", st.plain)
        self.assertIn("MEM%", st.plain)
        self.assertIn("COMMAND", st.plain)

    def test_process_data_shown(self):
        self.panel.update(MOCK_HEALTH, processes=MOCK_PROCESSES)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertIn("12.3", st.plain)
        self.assertIn("4.1", st.plain)
        self.assertIn("claw", st.plain)

    def test_empty_process_list(self):
        self.panel.update(MOCK_HEALTH, processes=[])
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertNotIn("Top Processes:", st.plain)

    def test_process_heading_is_grey(self):
        self.panel.update(MOCK_HEALTH, processes=MOCK_PROCESSES)
        st = self.panel._build_content(MOCK_HEALTH)
        heading_spans = [s for s in st._spans
                         if s.style == "table_heading"
                         and "Top Processes:" in st.plain[s.start:s.end]]
        self.assertTrue(len(heading_spans) >= 1,
                        "Process heading should use table_heading style")

    def test_process_table_heading_columns_are_grey(self):
        self.panel.update(MOCK_HEALTH, processes=MOCK_PROCESSES)
        st = self.panel._build_content(MOCK_HEALTH)
        heading_spans = [s for s in st._spans if s.style == "table_heading"]
        heading_text = "".join(st.plain[s.start:s.end] for s in heading_spans)
        self.assertIn("PID", heading_text)
        self.assertIn("COMMAND", heading_text)

    def test_max_five_processes(self):
        many_procs = MOCK_PROCESSES + [
            {"pid": "9999", "user": "test", "cpu": "0.1", "mem": "0.1",
             "command": "extra"},
            {"pid": "8888", "user": "test", "cpu": "0.1", "mem": "0.1",
             "command": "extra2"},
        ]
        self.panel.update(MOCK_HEALTH, processes=many_procs)
        st = self.panel._build_content(MOCK_HEALTH)
        self.assertNotIn("extra2", st.plain)


class TestServerSparkline(unittest.TestCase):
    """Test sparkline generation."""

    def test_empty_values(self):
        result = ServerHealthPanel._make_sparkline([])
        self.assertEqual(len(result), 16)

    def test_all_zeros(self):
        result = ServerHealthPanel._make_sparkline([0, 0, 0])
        self.assertTrue(all(c == "\u2581" for c in result))

    def test_increasing_values(self):
        result = ServerHealthPanel._make_sparkline([0, 25, 50, 75, 100])
        self.assertEqual(result[-1], "\u2588")

    def test_width_limit(self):
        values = list(range(30))
        result = ServerHealthPanel._make_sparkline(values, width=10)
        self.assertEqual(len(result), 10)

    def test_bar_color_thresholds(self):
        self.assertEqual(ServerHealthPanel._bar_color(95), "red")
        self.assertEqual(ServerHealthPanel._bar_color(80), "yellow")
        self.assertEqual(ServerHealthPanel._bar_color(50), "green")


# ---------------------------------------------------------------------------
# Agent panel tests
# ---------------------------------------------------------------------------

class TestAgentPanel(unittest.TestCase):
    """Test AgentFleetPanel with mock data."""

    def test_table_heading_is_grey(self):
        panel = AgentFleetPanel()
        data = {"agents": [
            {"name": "main", "model": "opus-4-6", "storage": "27M",
             "tokens": "126k", "sessions": 3, "is_default": True},
        ]}
        status = {"sessions": 3, "gateway_status": "running", "version": "1.0"}
        st = panel._build_content(data, status)
        heading_spans = [s for s in st._spans if s.style == "table_heading"]
        self.assertTrue(len(heading_spans) >= 1,
                        "Agent table heading should use table_heading style")

    def test_agent_names_displayed(self):
        panel = AgentFleetPanel()
        data = {"agents": [
            {"name": "main", "model": "opus-4-6", "storage": "27M",
             "tokens": "126k", "sessions": 3, "is_default": True},
            {"name": "raven", "model": "haiku-4-5", "storage": "5M",
             "tokens": "40k", "sessions": 1, "is_default": False},
        ]}
        status = {"sessions": 4, "gateway_status": "running"}
        st = panel._build_content(data, status)
        self.assertIn("main", st.plain)
        self.assertIn("raven", st.plain)

    def test_default_agent_marked(self):
        panel = AgentFleetPanel()
        data = {"agents": [
            {"name": "main", "model": "opus-4-6", "storage": "27M",
             "tokens": "126k", "sessions": 3, "is_default": True},
        ]}
        status = {"sessions": 3, "gateway_status": "running"}
        st = panel._build_content(data, status)
        self.assertIn("main*", st.plain)

    def test_gateway_status_displayed(self):
        panel = AgentFleetPanel()
        data = {"agents": [
            {"name": "main", "model": "opus-4-6", "storage": "27M",
             "tokens": "126k", "sessions": 3, "is_default": True},
        ]}
        status = {"sessions": 3, "gateway_status": "running"}
        st = panel._build_content(data, status)
        self.assertIn("Gateway: running", st.plain)

    def test_no_agents_message(self):
        panel = AgentFleetPanel()
        data = {"agents": [], "error": None}
        status = {"sessions": 0, "gateway_status": "unknown"}
        st = panel._build_content(data, status)
        self.assertIn("No agents found", st.plain)

    def test_error_loading_agents(self):
        panel = AgentFleetPanel()
        data = {"agents": [], "error": "connection refused"}
        status = {"sessions": 0, "gateway_status": "unknown"}
        st = panel._build_content(data, status)
        self.assertIn("Error loading agents", st.plain)


# ---------------------------------------------------------------------------
# Security panel tests
# ---------------------------------------------------------------------------

class TestSecurityPanel(unittest.TestCase):
    """Test SecurityPanel heading styles."""

    def test_ssh_logins_heading_is_grey(self):
        panel = SecurityPanel()
        panel.ssh_summary = {
            "accepted": [{"ip": "1.2.3.4", "count": 5, "hostname": "test"}],
            "failed": [],
        }
        data = {"ssh_intrusions": 0, "ports_detail": []}
        st = panel._build_content(data)
        heading_spans = [s for s in st._spans
                         if s.style == "table_heading"
                         and "SSH Logins" in st.plain[s.start:s.end]]
        self.assertTrue(len(heading_spans) >= 1)

    def test_ssh_failed_heading_is_grey(self):
        panel = SecurityPanel()
        panel.ssh_summary = {"accepted": [], "failed": []}
        data = {"ssh_intrusions": 0, "ports_detail": []}
        st = panel._build_content(data)
        heading_spans = [s for s in st._spans
                         if s.style == "table_heading"
                         and "SSH Failed" in st.plain[s.start:s.end]]
        self.assertTrue(len(heading_spans) >= 1)

    def test_no_intrusions_green(self):
        panel = SecurityPanel()
        panel.ssh_summary = {"accepted": [], "failed": []}
        data = {"ssh_intrusions": 0, "ports_detail": []}
        st = panel._build_content(data)
        self.assertIn("No intrusions", st.plain)

    def test_many_intrusions_red(self):
        panel = SecurityPanel()
        panel.ssh_summary = {"accepted": [], "failed": []}
        data = {"ssh_intrusions": 50, "ports_detail": []}
        st = panel._build_content(data)
        self.assertIn("50 failed attempts", st.plain)
        red_spans = [s for s in st._spans if s.style == "red"]
        self.assertTrue(len(red_spans) >= 1)


# ---------------------------------------------------------------------------
# Process collector tests
# ---------------------------------------------------------------------------

class TestTopProcessesCollector(unittest.TestCase):
    """Test get_top_processes with mocked subprocess."""

    def test_parses_ps_output(self):
        import asyncio
        from galactic_cic.data.collectors import get_top_processes

        mock_output = (
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "claw     51818 12.3  4.1 123456 78900 ?        Sl   Feb20  50:23 /opt/openclaw/gateway\n"
            "claw    809912  8.7  2.3 654321 45600 ?        Sl   Feb20  30:12 /opt/claude/bin/claude\n"
        )

        async def mock_run(cmd, **kwargs):
            return (mock_output, "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_top_processes(count=5))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pid"], "51818")
        self.assertEqual(result[0]["cpu"], "12.3")
        self.assertEqual(result[0]["mem"], "4.1")
        self.assertIn("gateway", result[0]["command"])

    def test_handles_empty_output(self):
        import asyncio
        from galactic_cic.data.collectors import get_top_processes

        async def mock_run(cmd, **kwargs):
            return ("", "", 1)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_top_processes())

        self.assertEqual(result, [])

    def test_handles_header_only(self):
        import asyncio
        from galactic_cic.data.collectors import get_top_processes

        async def mock_run(cmd, **kwargs):
            return ("USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n", "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_top_processes())

        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# StyledText merge test
# ---------------------------------------------------------------------------

class TestStyledTextMerge(unittest.TestCase):
    """Test that StyledText preserves styles when merging."""

    def test_append_preserves_single_style(self):
        st = StyledText()
        st.append("hello", "green")
        self.assertEqual(len(st._spans), 1)
        self.assertEqual(st._spans[0].style, "green")

    def test_manual_merge_preserves_styles(self):
        st1 = StyledText()
        st1.append("header\n", "table_heading")
        st1.append("data\n", "green")

        st2 = StyledText()
        offset = len(st2._text)
        st2._text += st1._text
        for span in st1._spans:
            st2._spans.append(StyledText.Span(
                span.start + offset, span.end + offset, span.style
            ))

        self.assertEqual(len(st2._spans), 2)
        self.assertEqual(st2._spans[0].style, "table_heading")
        self.assertEqual(st2._spans[1].style, "green")

    def test_plain_returns_raw_text(self):
        st = StyledText()
        st.append("hello ", "green")
        st.append("world", "red")
        self.assertEqual(st.plain, "hello world")


# ---------------------------------------------------------------------------
# Cron parser tests (Doctor diagnostic output filtering)
# ---------------------------------------------------------------------------

class TestCronParserDoctorOutput(unittest.TestCase):
    """Test get_cron_jobs handles Doctor diagnostic output before table."""

    def test_skips_doctor_output(self):
        """Parser should skip Doctor diagnostic box and find the real header."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        mock_output = (
            "│\n"
            "◇  Doctor changes ──────────────────────────────╮\n"
            "│                                               │\n"
            "│  WhatsApp configured, enabled automatically.  │\n"
            "│                                               │\n"
            "├───────────────────────────────────────────────╯\n"
            "│\n"
            "◇  Unknown config keys ─────────╮\n"
            "│  some.weird.key               │\n"
            "├───────────────────────────────╯\n"
            "│\n"
            "ID                                   Name                     Schedule    Next        Last        Status           Target          Agent\n"
            "abc123def456                         daily-backup             0 2 * * *   02:00:00    02:00:01    ok               /backups        main\n"
            "xyz789abc012                         log-rotate               0 6 * * *   06:00:00    06:00:02    ok               /var/log        main\n"
        )

        async def mock_run(cmd, **kwargs):
            return (mock_output, "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 2)
        self.assertEqual(result["jobs"][0]["name"], "daily-backup")
        self.assertEqual(result["jobs"][0]["status"], "ok")
        self.assertEqual(result["jobs"][1]["name"], "log-rotate")
        self.assertIsNone(result["error"])

    def test_handles_no_doctor_output(self):
        """Parser should still work when there's no Doctor output."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        mock_output = (
            "ID                                   Name                     Schedule    Next        Last        Status           Target          Agent\n"
            "abc123def456                         daily-backup             0 2 * * *   02:00:00    02:00:01    ok               /backups        main\n"
        )

        async def mock_run(cmd, **kwargs):
            return (mock_output, "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["name"], "daily-backup")

    def test_handles_only_doctor_output_no_table(self):
        """If Doctor output but no table header, return empty jobs."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        mock_output = (
            "│\n"
            "◇  Doctor changes ──────────────────────────────╮\n"
            "│  Some diagnostic message.                     │\n"
            "├───────────────────────────────────────────────╯\n"
        )

        async def mock_run(cmd, **kwargs):
            return (mock_output, "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 0)

    def test_handles_error_status_after_doctor(self):
        """Parser should correctly parse error status after Doctor output."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        mock_output = (
            "◇  Doctor changes ──────────────────────────────╮\n"
            "│  Config updated.                              │\n"
            "├───────────────────────────────────────────────╯\n"
            "ID                                   Name                     Schedule    Next        Last        Status           Target          Agent\n"
            "abc123def456                         failing-job              0 3 * * *   03:00:00    03:15:00    error            /tmp            main\n"
        )

        async def mock_run(cmd, **kwargs):
            return (mock_output, "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 1)
        self.assertEqual(result["jobs"][0]["name"], "failing-job")
        self.assertEqual(result["jobs"][0]["status"], "error")

    def test_handles_empty_output(self):
        """Parser handles empty/blank output gracefully."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        async def mock_run(cmd, **kwargs):
            return ("", "", 0)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 0)

    def test_handles_command_failure(self):
        """Parser handles command failure gracefully."""
        import asyncio
        from galactic_cic.data.collectors import get_cron_jobs

        async def mock_run(cmd, **kwargs):
            return ("", "command not found", 127)

        with patch("galactic_cic.data.collectors.run_command", side_effect=mock_run):
            result = asyncio.run(get_cron_jobs())

        self.assertEqual(len(result["jobs"]), 0)


# ---------------------------------------------------------------------------
# Sparkline rolling history tests
# ---------------------------------------------------------------------------

class TestSparklineRollingHistory(unittest.TestCase):
    """Test that sparkline history updates correctly with rolling data."""

    def test_sparkline_scrolls_with_new_data(self):
        """Each new value should appear as the rightmost sparkline character."""
        panel = ServerHealthPanel()
        # Simulate 5 refreshes with increasing values
        for i in range(5):
            panel.cpu_history.append(i * 20)
        sparkline = panel._make_sparkline(panel.cpu_history)
        self.assertEqual(len(sparkline), 5)
        # Last char should be highest (full block)
        self.assertEqual(sparkline[-1], "\u2588")
        # First char should be lowest (bottom block)
        self.assertEqual(sparkline[0], "\u2581")

    def test_sparkline_width_limits_output(self):
        """Sparkline should only show last N values where N = width."""
        panel = ServerHealthPanel()
        panel.cpu_history = list(range(30))
        sparkline = panel._make_sparkline(panel.cpu_history, width=10)
        self.assertEqual(len(sparkline), 10)

    def test_sparkline_single_value(self):
        """Single value should produce a single-char sparkline."""
        sparkline = ServerHealthPanel._make_sparkline([50])
        self.assertEqual(len(sparkline), 1)

    def test_rolling_history_capped_at_max(self):
        """Verify that history trimming works at boundary."""
        # Simulate the trimming logic from app.py
        history = list(range(70))
        max_len = 60
        if len(history) > max_len:
            history = history[-max_len:]
        self.assertEqual(len(history), 60)
        self.assertEqual(history[0], 10)  # oldest kept value
        self.assertEqual(history[-1], 69)  # newest value

    def test_sparkline_all_same_values(self):
        """All same values should produce uniform sparkline."""
        sparkline = ServerHealthPanel._make_sparkline([50, 50, 50, 50])
        # All should be top block since max == min == 50, and 50/50 * 7 = 7
        self.assertTrue(all(c == "\u2588" for c in sparkline))


# ---------------------------------------------------------------------------
# Security panel NMAP indicator tests
# ---------------------------------------------------------------------------

class TestSecurityNmapIndicator(unittest.TestCase):
    """Test NMAP indicator and attacker scan summary in security panel."""

    def test_nmap_title_changes_when_scanning(self):
        panel = SecurityPanel()
        panel.nmap_scanning = True
        self.assertEqual(panel.TITLE_NMAP, "Security Status [NMAP]")

    def test_attacker_scans_displayed(self):
        panel = SecurityPanel()
        panel.ssh_summary = {"accepted": [], "failed": []}
        panel.attacker_scans = {
            "1.2.3.4": {"open_ports": "22,80", "os_guess": "Linux"},
        }
        panel.geo_data = {"1.2.3.4": {"country_code": "CN"}}
        data = {"ssh_intrusions": 5, "ports_detail": []}
        st = panel._build_content(data)
        self.assertIn("Attacker Scans", st.plain)
        self.assertIn("1.2.3.4", st.plain)
        self.assertIn("22,80", st.plain)
        self.assertIn("[CN]", st.plain)

    def test_no_attacker_scans_shows_clear(self):
        panel = SecurityPanel()
        panel.ssh_summary = {"accepted": [], "failed": []}
        panel.attacker_scans = {}
        panel.last_nmap_time = "14:30:00"
        data = {"ssh_intrusions": 0, "ports_detail": []}
        st = panel._build_content(data)
        self.assertIn("No attackers scanned", st.plain)


# ---------------------------------------------------------------------------
# Activity panel IP summary tests
# ---------------------------------------------------------------------------

class TestActivityIPSummary(unittest.TestCase):
    """Test external IP summary in activity panel."""

    def test_update_accepts_ext_ip_summary(self):
        panel = ActivityLogPanel()
        summary = [
            {"ip": "1.2.3.4", "hostname": "example.com", "country": "US",
             "ports": "22,80"},
        ]
        panel.update([], errors=[], ext_ip_summary=summary)
        self.assertEqual(len(panel.ext_ip_summary), 1)
        self.assertEqual(panel.ext_ip_summary[0]["ip"], "1.2.3.4")

    def test_empty_ip_summary(self):
        panel = ActivityLogPanel()
        panel.update([], errors=[], ext_ip_summary=[])
        self.assertEqual(panel.ext_ip_summary, [])

    def test_ip_summary_preserved_across_updates(self):
        panel = ActivityLogPanel()
        summary = [{"ip": "5.6.7.8", "hostname": "test.net",
                     "country": "DE", "ports": "443"}]
        panel.update([], ext_ip_summary=summary)
        # Update without ip summary should preserve existing
        panel.update([{"time": "12:00", "message": "test", "type": "ssh",
                       "level": "info"}])
        self.assertEqual(len(panel.ext_ip_summary), 1)



# ---------------------------------------------------------------------------
# SITREP panel tests
# ---------------------------------------------------------------------------

class TestSitrepPanel(unittest.TestCase):
    """Tests for the SITREP panel (channels, updates, action items)."""

    def setUp(self):
        _init_theme_for_test()

    def test_panel_has_title(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        self.assertEqual(panel.TITLE, "SITREP")

    def test_update_channels(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        channels = [
            {"name": "Discord", "state": "OK", "detail": "connected"},
            {"name": "WhatsApp", "state": "WARN", "detail": "Not linked"},
        ]
        panel.update(channels=channels)
        self.assertEqual(len(panel.channels), 2)
        self.assertEqual(panel.channels[0]["name"], "Discord")

    def test_update_info(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(update_info={"available": True, "current": "1.0", "latest": "2.0"})
        self.assertTrue(panel.update_info["available"])
        self.assertEqual(panel.update_info["latest"], "2.0")

    def test_update_action_items(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        items = [
            {"severity": "error", "text": "Cron failed"},
            {"severity": "warn", "text": "Update available"},
        ]
        panel.update(action_items=items)
        self.assertEqual(len(panel.action_items), 2)

    def test_build_content_with_channels(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(
            channels=[
                {"name": "Discord", "state": "OK", "detail": "token ok"},
                {"name": "WhatsApp", "state": "WARN", "detail": "Not linked"},
            ],
            update_info={"available": True, "current": "1.0", "latest": "2.0"},
            action_items=[
                {"severity": "error", "text": "OpenClaw Update Check cron failed"},
            ],
        )
        content = panel._build_content()
        text = content.plain
        self.assertIn("Discord", text)
        self.assertIn("WhatsApp", text)
        self.assertIn("UPDATE AVAILABLE", text)
        self.assertIn("cron failed", text)

    def test_build_content_ok_channels(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(
            channels=[{"name": "Discord", "state": "OK", "detail": "ok"}],
        )
        content = panel._build_content()
        self.assertIn("●", content.plain)

    def test_build_content_warn_channel_style(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(
            channels=[{"name": "WhatsApp", "state": "WARN", "detail": "not linked"}],
        )
        content = panel._build_content()
        self.assertIn("▲", content.plain)
        # Check yellow styling
        styles = [s.style for s in content._spans]
        self.assertIn("yellow", styles)

    def test_build_content_no_update(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(update_info={"available": False})
        content = panel._build_content()
        self.assertIn("Up to date", content.plain)

    def test_build_content_empty_action_items(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(action_items=[])
        content = panel._build_content()
        self.assertIn("ALL CLEAR", content.plain)

    def test_build_content_error_action_item_style(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(action_items=[{"severity": "error", "text": "Critical failure"}])
        content = panel._build_content()
        self.assertIn("✖", content.plain)
        styles = [s.style for s in content._spans]
        self.assertIn("red", styles)

    def test_build_content_no_channels(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(channels=[])
        content = panel._build_content()
        self.assertIn("No channels configured", content.plain)

    def test_preserves_existing_data_on_partial_update(self):
        from galactic_cic.panels.sitrep import SitrepPanel
        panel = SitrepPanel()
        panel.update(channels=[{"name": "Discord", "state": "OK", "detail": "ok"}])
        panel.update(action_items=[{"severity": "warn", "text": "test"}])
        # Channels should still be there
        self.assertEqual(len(panel.channels), 1)
        self.assertEqual(len(panel.action_items), 1)


# ---------------------------------------------------------------------------
# Mock collector tests (build_action_items)
# ---------------------------------------------------------------------------

class TestBuildActionItems(unittest.TestCase):
    """Tests for the build_action_items aggregator."""

    def test_detects_cron_errors(self):
        from galactic_cic.data.collectors import build_action_items
        cron = {"jobs": [{"name": "Test Job", "status": "error"}]}
        items = build_action_items(cron, {}, [], {"available": False}, {})
        texts = [i["text"] for i in items]
        self.assertTrue(any("Test Job" in t for t in texts))

    def test_detects_update_available(self):
        from galactic_cic.data.collectors import build_action_items
        items = build_action_items(
            {"jobs": []}, {}, [],
            {"available": True, "latest": "2.0"}, {},
        )
        texts = [i["text"] for i in items]
        self.assertTrue(any("2.0" in t for t in texts))

    def test_detects_channel_warn(self):
        from galactic_cic.data.collectors import build_action_items
        channels = [{"name": "WhatsApp", "state": "WARN", "detail": "Not linked"}]
        items = build_action_items(
            {"jobs": []}, {}, channels, {"available": False}, {},
        )
        texts = [i["text"] for i in items]
        self.assertTrue(any("WhatsApp" in t for t in texts))

    def test_detects_high_disk(self):
        from galactic_cic.data.collectors import build_action_items
        items = build_action_items(
            {"jobs": []}, {}, [], {"available": False},
            {"disk_percent": 85},
        )
        texts = [i["text"] for i in items]
        self.assertTrue(any("Disk" in t for t in texts))

    def test_detects_high_ssh_intrusions(self):
        from galactic_cic.data.collectors import build_action_items
        items = build_action_items(
            {"jobs": []}, {"ssh_intrusions": 100}, [],
            {"available": False}, {},
        )
        texts = [i["text"] for i in items]
        self.assertTrue(any("SSH" in t for t in texts))

    def test_no_items_when_all_clear(self):
        from galactic_cic.data.collectors import build_action_items
        items = build_action_items(
            {"jobs": [{"name": "ok", "status": "ok"}]},
            {"ssh_intrusions": 0, "listening_ports": 4, "expected_ports": 4},
            [{"name": "Discord", "state": "OK"}],
            {"available": False},
            {"cpu_percent": 5, "mem_percent": 10, "disk_percent": 3},
        )
        self.assertEqual(len(items), 0)

    def test_multiple_items_combined(self):
        from galactic_cic.data.collectors import build_action_items
        items = build_action_items(
            {"jobs": [{"name": "Broken", "status": "error"}]},
            {"ssh_intrusions": 200},
            [{"name": "WA", "state": "WARN", "detail": "down"}],
            {"available": True, "latest": "3.0"},
            {"disk_percent": 95, "cpu_percent": 95, "mem_percent": 95},
        )
        # Should detect: cron error, ssh, channel warn, update, disk, mem, cpu
        self.assertGreaterEqual(len(items), 5)


if __name__ == "__main__":
    unittest.main()
