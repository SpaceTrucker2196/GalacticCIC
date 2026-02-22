Feature: Activity Log Display
  As an OpenClaw operator
  I want to see recent system activity
  So I can track what's happening on the system

  Scenario: Display recent events
    Given there are 5 recent activity events
    When the activity panel refreshes
    Then I should see 5 events in the log

  Scenario: Color code events by level
    Given there is an event with level "error"
    When the activity panel renders the event
    Then the event should be displayed in red

  Scenario: Filter activity log
    Given there are events with different types
    When I filter the activity log by "ssh"
    Then I should only see SSH-related events
