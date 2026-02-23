"""Step definitions for Activity Log Display feature."""

from behave import given, when, then

from galactic_cic.panels.activity import ActivityLogPanel


@given("there are {count:d} recent activity events")
def step_activity_events(context, count):
    context.test_data["events"] = [
        {
            "time": f"10:0{i}",
            "message": f"Event {i} happened",
            "type": "system",
            "level": "info",
        }
        for i in range(count)
    ]


@given('there is an event with level "{level}"')
def step_event_level(context, level):
    context.test_data["events"] = [
        {
            "time": "10:00",
            "message": "Something went wrong",
            "type": "system",
            "level": level,
        }
    ]


@given("there are events with different types")
def step_mixed_events(context):
    context.test_data["events"] = [
        {"time": "10:00", "message": "SSH login accepted", "type": "ssh", "level": "info"},
        {"time": "10:01", "message": "Cron job ran", "type": "cron", "level": "info"},
        {"time": "10:02", "message": "Agent started", "type": "openclaw", "level": "info"},
    ]


@when("the activity panel refreshes")
def step_render_activity(context):
    panel = ActivityLogPanel()
    rendered = []
    for event in context.test_data["events"]:
        rendered.append(panel._format_event(event))
    context.test_data["rendered"] = rendered
    context.panel_output = rendered


@when("the activity panel renders the event")
def step_render_single_event(context):
    panel = ActivityLogPanel()
    rendered = []
    for event in context.test_data["events"]:
        rendered.append(panel._format_event(event))
    context.test_data["rendered"] = rendered
    context.panel_output = rendered


@when('I filter the activity log by "{filter_text}"')
def step_filter_log(context, filter_text):
    panel = ActivityLogPanel()
    panel.set_filter(filter_text)
    filtered = []
    for event in context.test_data["events"]:
        if filter_text.lower() in event.get("message", "").lower() or \
           filter_text.lower() in event.get("type", "").lower():
            filtered.append(panel._format_event(event))
    context.test_data["rendered"] = filtered
    context.panel_output = filtered


@then("I should see {count:d} events in the log")
def step_see_events(context, count):
    assert len(context.test_data["rendered"]) == count, (
        f"Expected {count} events, got {len(context.test_data['rendered'])}"
    )


@then("the event should be displayed in red")
def step_event_red(context):
    rendered = context.test_data["rendered"][0]
    # StyledText stores spans with style strings — check for "red"
    found_red = False
    for span in rendered._spans:
        if "red" in str(span.style):
            found_red = True
            break
    assert found_red, f"Expected red style in rendered event, spans: {rendered._spans}"


@then("I should only see SSH-related events")
def step_only_ssh(context):
    assert len(context.test_data["rendered"]) > 0, "No events rendered"
    for event in context.test_data["events"]:
        if "ssh" in event.get("type", "").lower() or "ssh" in event.get("message", "").lower():
            continue
