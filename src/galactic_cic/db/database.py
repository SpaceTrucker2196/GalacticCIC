"""SQLite database connection, schema, and migrations for GalacticCIC."""

import os
import sqlite3
import time


# Default database location
DEFAULT_DB_DIR = os.path.expanduser("~/.galactic_cic")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "metrics.db")

# Schema version
SCHEMA_VERSION = 1

# Retention: 30 days in seconds
RETENTION_SECONDS = 30 * 24 * 3600

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    agent_name TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    sessions INTEGER DEFAULT 0,
    storage_bytes INTEGER DEFAULT 0,
    model TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS server_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    cpu_percent REAL DEFAULT 0,
    mem_used_mb REAL DEFAULT 0,
    mem_total_mb REAL DEFAULT 0,
    disk_used_gb REAL DEFAULT 0,
    disk_total_gb REAL DEFAULT 0,
    load_1m REAL DEFAULT 0,
    load_5m REAL DEFAULT 0,
    load_15m REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cron_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    job_name TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    last_run TEXT DEFAULT '',
    next_run TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS security_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    ssh_intrusions INTEGER DEFAULT 0,
    ports_open INTEGER DEFAULT 0,
    ufw_active INTEGER DEFAULT 0,
    fail2ban_active INTEGER DEFAULT 0,
    root_login_enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS port_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    port INTEGER NOT NULL,
    service TEXT DEFAULT '',
    state TEXT DEFAULT 'open'
);

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

CREATE INDEX IF NOT EXISTS idx_agent_ts ON agent_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_server_ts ON server_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_security_ts ON security_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_network_ts ON network_metrics(timestamp);
"""


class MetricsDB:
    """SQLite database for historical metrics storage."""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path

        # Ensure directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # WAL mode for concurrent reads during writes
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        """Create tables and run migrations."""
        cursor = self.conn.cursor()
        # Execute schema creation
        cursor.executescript(SCHEMA_SQL)

        # Check/set schema version
        cursor.execute("SELECT COUNT(*) FROM schema_version")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        self.conn.commit()

    def execute(self, sql, params=()):
        """Execute a SQL statement and return cursor."""
        return self.conn.execute(sql, params)

    def executemany(self, sql, params_list):
        """Execute a SQL statement with multiple parameter sets."""
        return self.conn.executemany(sql, params_list)

    def commit(self):
        """Commit pending transaction."""
        self.conn.commit()

    def fetchone(self, sql, params=()):
        """Execute and fetch one row."""
        cursor = self.conn.execute(sql, params)
        return cursor.fetchone()

    def fetchall(self, sql, params=()):
        """Execute and fetch all rows."""
        cursor = self.conn.execute(sql, params)
        return cursor.fetchall()

    def prune(self, max_age_seconds=None):
        """Delete records older than max_age_seconds (default 30 days)."""
        if max_age_seconds is None:
            max_age_seconds = RETENTION_SECONDS
        cutoff = time.time() - max_age_seconds
        tables = [
            "agent_metrics", "server_metrics", "cron_metrics",
            "security_metrics", "port_scans", "network_metrics",
        ]
        for table in tables:
            self.conn.execute(
                f"DELETE FROM {table} WHERE timestamp < ?", (cutoff,)
            )
        # dns_cache uses resolved_at instead of timestamp
        self.conn.execute(
            "DELETE FROM dns_cache WHERE resolved_at < ?", (cutoff,)
        )
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
