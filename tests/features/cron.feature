Feature: Cron Job Display
  As an OpenClaw operator
  I want to see cron job status
  So I can catch failures quickly

  Scenario: Display all cron jobs with status
    Given there are 5 cron jobs configured
    When the cron panel loads
    Then I should see 5 cron jobs listed
    And each should show status icon, name, and timing

  Scenario: Highlight error jobs
    Given cron job "Deal Flow Scanner" has status "error"
    When the cron panel renders
    Then "Deal Flow Scanner" should be displayed in red
    And it should show the error icon

  Scenario: Show consecutive error count
    Given a cron job has 12 consecutive errors
    When the cron panel renders
    Then I should see the error count "12"
