"""Step definitions for Historical Metrics Database feature."""

import os
import tempfile
import time

from behave import given, when, then

from galactic_cic.db.database import MetricsDB
from galactic_cic.db.recorder import MetricsRecorder
from galactic_cic.db.trends import TrendCalculator


@given("the database module is available")
def step_db_module(context):
    context.test_data["db_available"] = True


@when("I create a MetricsDB instance")
def step_create_db(context):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    context.test_data["tmpdir"] = tmpdir
    context.test_data["db_path"] = db_path
    context.test_data["db"] = MetricsDB(db_path=db_path)


@then("the database file should exist")
def step_db_exists(context):
    assert os.path.exists(context.test_data["db_path"]), "DB file not created"


@then("the schema should be initialized")
def step_schema_init(context):
    db = context.test_data["db"]
    row = db.fetchone("SELECT version FROM schema_version")
    assert row is not None, "Schema version not set"
    assert row["version"] == 1
    db.close()


@given("a fresh metrics database")
def step_fresh_db(context):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    context.test_data["tmpdir"] = tmpdir
    context.test_data["db_path"] = db_path
    context.test_data["db"] = MetricsDB(db_path=db_path)
    context.test_data["recorder"] = MetricsRecorder(context.test_data["db"])


@when('I record agent metrics for "{name}" with {tokens:d} tokens')
def step_record_agent(context, name, tokens):
    recorder = context.test_data["recorder"]
    recorder.record_agents({
        "agents": [
            {"name": name, "tokens_numeric": tokens, "sessions": 3,
             "storage_bytes": 27000000, "model": "opus-4-6"},
        ]
    })


@then("I should find the agent record in the database")
def step_find_agent(context):
    db = context.test_data["db"]
    row = db.fetchone("SELECT * FROM agent_metrics WHERE agent_name = 'main'")
    assert row is not None, "Agent record not found"
    assert row["tokens_used"] == 126000
    db.close()


@given("a database with agent token history")
def step_db_with_history(context):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    db = MetricsDB(db_path=db_path)
    context.test_data["tmpdir"] = tmpdir
    context.test_data["db_path"] = db_path
    context.test_data["db"] = db
    context.test_data["trends"] = TrendCalculator(db)
    now = time.time()
    db.execute(
        "INSERT INTO agent_metrics "
        "(timestamp, agent_name, tokens_used, sessions) VALUES (?, ?, ?, ?)",
        (now - 1800, "main", 100000, 3),
    )
    db.execute(
        "INSERT INTO agent_metrics "
        "(timestamp, agent_name, tokens_used, sessions) VALUES (?, ?, ?, ?)",
        (now, "main", 150000, 3),
    )
    db.commit()


@when("I calculate tokens per hour")
def step_calc_tph(context):
    trends = context.test_data["trends"]
    context.test_data["tph_result"] = trends.get_agent_tokens_per_hour()


@then("the result should be greater than zero")
def step_tph_positive(context):
    result = context.test_data["tph_result"]
    assert result["_total"] > 0, f"Expected positive total, got {result['_total']}"
    context.test_data["db"].close()


@given("a database with server metrics over time")
def step_db_server_history(context):
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    db = MetricsDB(db_path=db_path)
    context.test_data["tmpdir"] = tmpdir
    context.test_data["db_path"] = db_path
    context.test_data["db"] = db
    context.test_data["trends"] = TrendCalculator(db)
    now = time.time()
    db.execute(
        "INSERT INTO server_metrics "
        "(timestamp, cpu_percent, mem_used_mb, disk_used_gb) VALUES (?, ?, ?, ?)",
        (now - 5400, 20.0, 3000.0, 30.0),
    )
    db.execute(
        "INSERT INTO server_metrics "
        "(timestamp, cpu_percent, mem_used_mb, disk_used_gb) VALUES (?, ?, ?, ?)",
        (now, 40.0, 3500.0, 30.0),
    )
    db.commit()


@when("I calculate server trends")
def step_calc_trends(context):
    trends = context.test_data["trends"]
    context.test_data["server_trends"] = trends.get_server_trends()


@then("I should see trend arrows for CPU, MEM, and DISK")
def step_see_arrows(context):
    result = context.test_data["server_trends"]
    assert result["cpu_trend"] != "--", f"CPU trend is '--'"
    assert result["mem_trend"] != "--", f"MEM trend is '--'"
    assert result["disk_trend"] != "--", f"DISK trend is '--'"
    context.test_data["db"].close()
