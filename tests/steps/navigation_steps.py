"""Step definitions for Keyboard Navigation feature."""

from behave import given, when, then

from galactic_cic.app import CICDashboard


@given("the dashboard is running")
def step_dashboard_running(context):
    context.test_data["app_class"] = CICDashboard


@when('I press "{key}"')
def step_press_key(context, key):
    context.test_data["key"] = key


@then("the dashboard should exit")
def step_should_exit(context):
    app_class = context.test_data["app_class"]
    bindings = {b.key: b.action for b in app_class.BINDINGS}
    assert "q" in bindings, "No 'q' binding found"
    assert bindings["q"] == "quit", f"'q' maps to '{bindings['q']}', expected 'quit'"


@then("all panels should refresh immediately")
def step_should_refresh(context):
    app_class = context.test_data["app_class"]
    bindings = {b.key: b.action for b in app_class.BINDINGS}
    assert "r" in bindings, "No 'r' binding found"
    assert bindings["r"] == "refresh_all", (
        f"'r' maps to '{bindings['r']}', expected 'refresh_all'"
    )


@then("the agent panel should be focused")
def step_agent_focused(context):
    app_class = context.test_data["app_class"]
    bindings = {b.key: b.action for b in app_class.BINDINGS}
    assert "1" in bindings, "No '1' binding found"
    assert "focus_panel" in bindings["1"], (
        f"'1' maps to '{bindings['1']}', expected focus_panel"
    )
