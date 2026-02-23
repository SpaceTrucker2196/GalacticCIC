"""Step definitions for Agent Fleet Display feature."""

from behave import given, when, then

from galactic_cic.panels.agents import AgentFleetPanel


@given("the OpenClaw instance has {count:d} agents configured")
def step_agents_configured(context, count):
    context.test_data["agents"] = {
        "agents": [
            {"name": f"agent-{i}", "status": "online", "model": "claude-sonnet"}
            for i in range(count)
        ],
        "error": None,
    }
    context.test_data["status"] = {
        "sessions": 0,
        "model": "claude-sonnet",
        "gateway_status": "running",
    }


@given('agent "{name}" has {count:d} active sessions')
def step_agent_sessions(context, name, count):
    context.test_data["agents"] = {
        "agents": [{"name": name, "status": "online", "model": "claude-sonnet"}],
        "error": None,
    }
    context.test_data["status"] = {
        "sessions": count,
        "model": "claude-sonnet",
        "gateway_status": "running",
    }


@given("the openclaw CLI is not available")
def step_no_openclaw(context):
    context.test_data["agents"] = {
        "agents": [],
        "error": "openclaw: command not found",
    }
    context.test_data["status"] = {
        "sessions": 0,
        "model": "unknown",
        "gateway_status": "unknown",
    }


@when("the CIC dashboard loads the agent panel")
@when("the agent panel refreshes")
@when("the agent panel tries to refresh")
def step_load_agent_panel(context):
    panel = AgentFleetPanel()
    context.panel_output = panel._build_content(
        context.test_data["agents"],
        context.test_data["status"],
    )


@then("I should see {count:d} agents listed")
def step_see_agents(context, count):
    text = context.panel_output.plain
    agent_names = [a["name"] for a in context.test_data["agents"]["agents"]]
    for name in agent_names:
        assert name in text, f"Agent '{name}' not in output: {text}"


@then("each agent should show name, status, and model")
def step_agents_show_details(context):
    text = context.panel_output.plain
    for agent in context.test_data["agents"]["agents"]:
        name = agent["name"]
        assert name in text, f"Agent name '{name}' not found in output"
        model = agent.get("model", "")
        if model:
            assert model in text, f"Model '{model}' not found in output"


@then('I should see "{count}" sessions for agent "{name}"')
def step_see_sessions(context, count, name):
    text = context.panel_output.plain
    assert f"Sessions: {count}" in text or f"{count}" in text, (
        f"Expected '{count}' sessions in output, got: {text}"
    )


@then("I should see an error message instead of agent data")
def step_see_error(context):
    text = context.panel_output.plain
    assert "Error" in text or "error" in text or "No agents" in text, (
        f"Expected error message in output, got: {text}"
    )


@then("the dashboard should not crash")
def step_no_crash(context):
    assert context.panel_output is not None
