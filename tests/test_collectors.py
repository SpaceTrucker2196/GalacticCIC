"""Unit tests for data collectors."""

import asyncio
import unittest

from galactic_cic.data.collectors import (
    run_command,
    get_server_health,
    get_agents_data,
    get_cron_jobs,
    get_security_status,
    get_activity_log,
    _parse_size,
)


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


class TestCollectors(unittest.TestCase):
    """Test collector functions handle graceful failures."""

    def test_server_health_returns_dict(self):
        result = asyncio.run(get_server_health())
        self.assertIsInstance(result, dict)
        self.assertIn("cpu_percent", result)
        self.assertIn("mem_percent", result)
        self.assertIn("disk_percent", result)

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


if __name__ == "__main__":
    unittest.main()
