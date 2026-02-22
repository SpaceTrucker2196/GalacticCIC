"""Step definitions for Security Status Display feature."""

from behave import given, when, then

from galactic_cic.panels.security import SecurityPanel


@given("there were {count:d} failed SSH logins in the last 24h")
def step_ssh_logins(context, count):
    context.test_data["security"] = {
        "ssh_intrusions": count,
        "listening_ports": 4,
        "expected_ports": 4,
        "ufw_active": True,
        "fail2ban_active": True,
        "root_login_enabled": False,
    }


@given("there are {count:d} listening ports")
def step_listening_ports(context, count):
    context.test_data["security"] = {
        "ssh_intrusions": 0,
        "listening_ports": count,
        "expected_ports": 4,
        "ufw_active": True,
        "fail2ban_active": True,
        "root_login_enabled": False,
    }


@when("the security panel refreshes")
def step_render_security(context):
    panel = SecurityPanel()
    context.panel_output = panel._render_content(context.test_data["security"])


@then('SSH status should show green with "{message}"')
def step_ssh_green(context, message):
    text = context.panel_output.plain
    assert message in text, f"Expected '{message}' in output, got: {text}"


@then("SSH status should show red with the count")
def step_ssh_red(context):
    text = context.panel_output.plain
    count = context.test_data["security"]["ssh_intrusions"]
    assert str(count) in text, f"Expected count '{count}' in output, got: {text}"
    assert "failed attempts" in text, f"Expected 'failed attempts' in output"


@then('I should see "{text_match}" ports')
def step_see_ports(context, text_match):
    text = context.panel_output.plain
    assert text_match in text, (
        f"Expected '{text_match}' in output, got: {text}"
    )
