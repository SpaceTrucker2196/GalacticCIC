Feature: Security Status Display
  As an OpenClaw operator
  I want to see security posture at a glance
  So I can identify threats quickly

  Scenario: Show SSH login status
    Given there were 0 failed SSH logins in the last 24h
    When the security panel refreshes
    Then SSH status should show green with "No intrusions"

  Scenario: Alert on high failed login count
    Given there were 500 failed SSH logins in the last 24h
    When the security panel refreshes
    Then SSH status should show red with the count

  Scenario: Show listening ports
    Given there are 4 listening ports
    When the security panel refreshes
    Then I should see "4 listening" ports
