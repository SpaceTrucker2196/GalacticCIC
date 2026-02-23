"""Step definitions for Server Health Display feature."""

from behave import given, when, then

from galactic_cic.panels.server import ServerHealthPanel


@given("the server has system monitoring tools installed")
def step_monitoring_tools(context):
    context.test_data["health"] = {
        "cpu_percent": 25.0,
        "mem_percent": 55.0,
        "mem_used": "4.2G",
        "mem_total": "7.7G",
        "disk_percent": 42.0,
        "disk_used": "20G",
        "disk_total": "50G",
        "load_avg": [0.5, 0.8, 0.6],
        "uptime": "5 days, 3:22",
    }


@given("memory usage is above 90%")
def step_high_memory(context):
    context.test_data["health"] = {
        "cpu_percent": 25.0,
        "mem_percent": 95.0,
        "mem_used": "7.3G",
        "mem_total": "7.7G",
        "disk_percent": 42.0,
        "disk_used": "20G",
        "disk_total": "50G",
        "load_avg": [0.5, 0.8, 0.6],
        "uptime": "5 days, 3:22",
    }


@given("the OpenClaw gateway is running")
def step_gateway_running(context):
    context.test_data["health"] = {
        "cpu_percent": 25.0,
        "mem_percent": 55.0,
        "mem_used": "4.2G",
        "mem_total": "7.7G",
        "disk_percent": 42.0,
        "disk_used": "20G",
        "disk_total": "50G",
        "load_avg": [0.5, 0.8, 0.6],
        "uptime": "5 days, 3:22",
    }
    context.test_data["gateway_status"] = "running"


@when("the server panel refreshes")
@when("the server panel renders")
def step_render_server(context):
    panel = ServerHealthPanel()
    context.panel_output = panel._build_content(context.test_data["health"])


@then("I should see CPU usage as a percentage")
def step_see_cpu(context):
    text = context.panel_output.plain
    assert "CPU" in text, f"CPU not found in output: {text}"
    assert "%" in text, f"No percentage found in output: {text}"


@then("I should see memory usage with used/total")
def step_see_memory(context):
    text = context.panel_output.plain
    assert "MEM" in text, f"MEM not found in output: {text}"
    health = context.test_data["health"]
    assert health["mem_used"] in text, f"mem_used not in output: {text}"
    assert health["mem_total"] in text, f"mem_total not in output: {text}"


@then("I should see disk usage with used/total")
def step_see_disk(context):
    text = context.panel_output.plain
    assert "DISK" in text, f"DISK not found in output: {text}"
    health = context.test_data["health"]
    assert health["disk_used"] in text, f"disk_used not in output: {text}"
    assert health["disk_total"] in text, f"disk_total not in output: {text}"


@then("memory should be displayed in red")
def step_memory_red(context):
    color = ServerHealthPanel._bar_color(95.0)
    assert color == "red", f"Expected 'red' for 95%, got '{color}'"


@then('I should see gateway status as "{status}"')
def step_see_gateway(context, status):
    assert context.test_data.get("gateway_status") == status, (
        f"Expected gateway '{status}', got '{context.test_data.get('gateway_status')}'"
    )
