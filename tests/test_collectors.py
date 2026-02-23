"""Unit tests for data collectors and database module."""

import asyncio
import os
import tempfile
import time
import unittest

from galactic_cic.data.collectors import (
    run_command,
    get_server_health,
    get_agents_data,
    get_cron_jobs,
    get_security_status,
    get_activity_log,
    _parse_size,
    _parse_storage_bytes,
)
from galactic_cic.db.database import MetricsDB
from galactic_cic.db.recorder import MetricsRecorder
from galactic_cic.db.trends import TrendCalculator, ARROW_UP, ARROW_STABLE, NO_DATA


class TestRunCommand(unittest.TestCase):
    """Test the run_command async helper."""

    def test_successful_command(self):
        stdout, stderr, rc = asyncio.run(run_command("echo hello"))
        self.assertEqual(rc, 0)
        self.assertIn("hello", stdout)

    def test_failing_command(self):
        stdout, stderr, rc = asyncio.run(run_command("false"))
        self.assertNotEqual(rc, 0)

    def test_missing_command(self):
        stdout, stderr, rc = asyncio.run(
            run_command("nonexistent_command_xyz 2>/dev/null")
        )
        # Should not raise, just return non-zero
        self.assertTrue(rc != 0 or stderr)

    def test_timeout(self):
        stdout, stderr, rc = asyncio.run(
            run_command("sleep 30", timeout=0.1)
        )
        self.assertNotEqual(rc, 0)


class TestParseSize(unittest.TestCase):
    """Test size string parsing."""

    def test_gigabytes(self):
        self.assertAlmostEqual(_parse_size("3.2G"), 3.2, places=1)

    def test_megabytes(self):
        self.assertAlmostEqual(_parse_size("512M"), 0.5, places=1)

    def test_terabytes(self):
        self.assertAlmostEqual(_parse_size("1T"), 1024.0, places=0)

    def test_invalid(self):
        self.assertEqual(_parse_size("abc"), 0.0)


class TestParseStorageBytes(unittest.TestCase):
    """Test storage bytes parsing."""

    def test_megabytes(self):
        self.assertEqual(_parse_storage_bytes("27M"), 27 * 1024 ** 2)

    def test_gigabytes(self):
        result = _parse_storage_bytes("3.2G")
        self.assertAlmostEqual(result, 3.2 * 1024 ** 3, delta=1024)

    def test_invalid(self):
        self.assertEqual(_parse_storage_bytes("abc"), 0)


class TestCollectors(unittest.TestCase):
    """Test collector functions handle graceful failures."""

    def test_server_health_returns_dict(self):
        result = asyncio.run(get_server_health())
        self.assertIsInstance(result, dict)
        self.assertIn("cpu_percent", result)
        self.assertIn("mem_percent", result)
        self.assertIn("disk_percent", result)
        # v3: numeric fields for DB
        self.assertIn("mem_used_mb", result)
        self.assertIn("mem_total_mb", result)
        self.assertIn("disk_used_gb", result)
        self.assertIn("disk_total_gb", result)

    def test_agents_data_returns_dict(self):
        result = asyncio.run(get_agents_data())
        self.assertIsInstance(result, dict)
        self.assertIn("agents", result)

    def test_cron_jobs_returns_dict(self):
        result = asyncio.run(get_cron_jobs())
        self.assertIsInstance(result, dict)
        self.assertIn("jobs", result)

    def test_security_status_returns_dict(self):
        result = asyncio.run(get_security_status())
        self.assertIsInstance(result, dict)
        self.assertIn("ssh_intrusions", result)

    def test_activity_log_returns_list(self):
        result = asyncio.run(get_activity_log())
        self.assertIsInstance(result, list)


class TestMetricsDB(unittest.TestCase):
    """Test the SQLite metrics database."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_metrics.db")
        self.db = MetricsDB(db_path=self.db_path)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    def test_db_creates_file(self):
        self.assertTrue(os.path.exists(self.db_path))

    def test_schema_version(self):
        row = self.db.fetchone("SELECT version FROM schema_version")
        self.assertEqual(row["version"], 1)

    def test_insert_and_fetch_server_metrics(self):
        ts = time.time()
        self.db.execute(
            "INSERT INTO server_metrics "
            "(timestamp, cpu_percent, mem_used_mb, mem_total_mb) "
            "VALUES (?, ?, ?, ?)",
            (ts, 25.0, 3200.0, 5500.0),
        )
        self.db.commit()
        row = self.db.fetchone(
            "SELECT * FROM server_metrics ORDER BY id DESC LIMIT 1"
        )
        self.assertAlmostEqual(row["cpu_percent"], 25.0)
        self.assertAlmostEqual(row["mem_used_mb"], 3200.0)

    def test_insert_and_fetch_agent_metrics(self):
        ts = time.time()
        self.db.execute(
            "INSERT INTO agent_metrics "
            "(timestamp, agent_name, tokens_used, sessions) "
            "VALUES (?, ?, ?, ?)",
            (ts, "main", 126000, 3),
        )
        self.db.commit()
        row = self.db.fetchone(
            "SELECT * FROM agent_metrics WHERE agent_name = 'main'"
        )
        self.assertEqual(row["tokens_used"], 126000)
        self.assertEqual(row["sessions"], 3)

    def test_prune_old_records(self):
        old_ts = time.time() - (31 * 24 * 3600)  # 31 days ago
        self.db.execute(
            "INSERT INTO server_metrics (timestamp, cpu_percent) VALUES (?, ?)",
            (old_ts, 50.0),
        )
        self.db.commit()
        self.db.prune()
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM server_metrics")
        self.assertEqual(row["cnt"], 0)

    def test_recent_records_survive_prune(self):
        ts = time.time()
        self.db.execute(
            "INSERT INTO server_metrics (timestamp, cpu_percent) VALUES (?, ?)",
            (ts, 50.0),
        )
        self.db.commit()
        self.db.prune()
        row = self.db.fetchone("SELECT COUNT(*) as cnt FROM server_metrics")
        self.assertEqual(row["cnt"], 1)


class TestMetricsRecorder(unittest.TestCase):
    """Test the metrics recorder."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_metrics.db")
        self.db = MetricsDB(db_path=self.db_path)
        self.recorder = MetricsRecorder(self.db)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    def test_record_agents(self):
        self.recorder.record_agents({
            "agents": [
                {"name": "main", "tokens_numeric": 126000, "sessions": 3,
                 "storage_bytes": 27000000, "model": "opus-4-6"},
            ]
        })
        row = self.db.fetchone("SELECT * FROM agent_metrics")
        self.assertEqual(row["agent_name"], "main")
        self.assertEqual(row["tokens_used"], 126000)

    def test_record_server(self):
        self.recorder.record_server({
            "cpu_percent": 23.0, "mem_used_mb": 3200.0,
            "mem_total_mb": 5500.0, "disk_used_gb": 32.0,
            "disk_total_gb": 40.0, "load_avg": [0.42, 0.38, 0.31],
        })
        row = self.db.fetchone("SELECT * FROM server_metrics")
        self.assertAlmostEqual(row["cpu_percent"], 23.0)

    def test_record_security(self):
        self.recorder.record_security({
            "ssh_intrusions": 5, "listening_ports": 4,
            "ufw_active": True, "fail2ban_active": True,
            "root_login_enabled": False, "ports_detail": [
                {"port": "22", "service": "ssh", "state": "open"},
            ],
        })
        row = self.db.fetchone("SELECT * FROM security_metrics")
        self.assertEqual(row["ssh_intrusions"], 5)
        port_row = self.db.fetchone("SELECT * FROM port_scans")
        self.assertEqual(port_row["port"], 22)


class TestTrendCalculator(unittest.TestCase):
    """Test trend calculations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_metrics.db")
        self.db = MetricsDB(db_path=self.db_path)
        self.trends = TrendCalculator(self.db)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        os.rmdir(self.tmpdir)

    def test_no_data_returns_dashes(self):
        result = self.trends.get_server_trends()
        self.assertEqual(result["cpu_trend"], NO_DATA)
        self.assertEqual(result["mem_trend"], NO_DATA)
        self.assertEqual(result["disk_trend"], NO_DATA)

    def test_tokens_per_hour_empty(self):
        result = self.trends.get_agent_tokens_per_hour()
        self.assertEqual(result["_total"], 0)

    def test_tokens_per_hour_calculation(self):
        now = time.time()
        # Insert data 30 minutes ago
        self.db.execute(
            "INSERT INTO agent_metrics "
            "(timestamp, agent_name, tokens_used, sessions) "
            "VALUES (?, ?, ?, ?)",
            (now - 1800, "main", 100000, 3),
        )
        # Insert current data
        self.db.execute(
            "INSERT INTO agent_metrics "
            "(timestamp, agent_name, tokens_used, sessions) "
            "VALUES (?, ?, ?, ?)",
            (now, "main", 150000, 3),
        )
        self.db.commit()
        result = self.trends.get_agent_tokens_per_hour()
        # 50k tokens in 0.5 hours = 100k/hr
        self.assertGreater(result.get("main", 0), 0)
        self.assertGreater(result["_total"], 0)

    def test_server_trends_with_data(self):
        now = time.time()
        # Old data (1.5 hours ago)
        self.db.execute(
            "INSERT INTO server_metrics "
            "(timestamp, cpu_percent, mem_used_mb, disk_used_gb) "
            "VALUES (?, ?, ?, ?)",
            (now - 5400, 20.0, 3000.0, 30.0),
        )
        # Current data
        self.db.execute(
            "INSERT INTO server_metrics "
            "(timestamp, cpu_percent, mem_used_mb, disk_used_gb) "
            "VALUES (?, ?, ?, ?)",
            (now, 40.0, 3500.0, 30.0),
        )
        self.db.commit()
        result = self.trends.get_server_trends()
        self.assertEqual(result["cpu_trend"], ARROW_UP)
        self.assertEqual(result["disk_trend"], ARROW_STABLE)


if __name__ == "__main__":
    unittest.main()
