"""Step definitions for Cron Job Display feature."""

from behave import given, when, then

from galactic_cic.panels.cron import CronJobsPanel


@given("there are {count:d} cron jobs configured")
def step_cron_configured(context, count):
    context.test_data["cron"] = {
        "jobs": [
            {
                "name": f"job-{i}",
                "status": "ok",
                "last_run": "2025-01-15 10:00",
                "error_count": 0,
            }
            for i in range(count)
        ],
        "error": None,
    }


@given('cron job "{name}" has status "{status}"')
def step_cron_error(context, name, status):
    context.test_data["cron"] = {
        "jobs": [
            {
                "name": name,
                "status": status,
                "last_run": "2025-01-15 10:00",
                "error_count": 3,
            }
        ],
        "error": None,
    }


@given("a cron job has {count:d} consecutive errors")
def step_cron_errors(context, count):
    context.test_data["cron"] = {
        "jobs": [
            {
                "name": "failing-job",
                "status": "error",
                "last_run": "2025-01-15 10:00",
                "error_count": count,
            }
        ],
        "error": None,
    }


@when("the cron panel loads")
@when("the cron panel renders")
def step_render_cron(context):
    panel = CronJobsPanel()
    context.panel_output = panel._build_content(context.test_data["cron"])


@then("I should see {count:d} cron jobs listed")
def step_see_cron_count(context, count):
    text = context.panel_output.plain
    job_lines = [
        line for line in text.split("\n")
        if line.strip() and "job-" in line
    ]
    assert len(job_lines) == count, (
        f"Expected {count} jobs, found {len(job_lines)}"
    )


@then("each should show status icon, name, and timing")
def step_cron_details(context):
    text = context.panel_output.plain
    for job in context.test_data["cron"]["jobs"]:
        assert job["name"] in text, f"Job '{job['name']}' not in output"


@then('"{name}" should be displayed in red')
def step_cron_red(context, name):
    text = context.panel_output.plain
    assert name in text, f"Job '{name}' not found in output: {text}"
    assert "\u274c" in text, "Error icon not found in output"


@then("it should show the error icon")
def step_error_icon(context):
    text = context.panel_output.plain
    assert "\u274c" in text, f"Error icon (\\u274c) not in output: {text}"


@then('I should see the error count "{count}"')
def step_error_count(context, count):
    text = context.panel_output.plain
    assert f"{count}err)" in text or f"{count} err" in text, (
        f"Expected '{count}err)' or '{count} err' in output, got: {text}"
    )
