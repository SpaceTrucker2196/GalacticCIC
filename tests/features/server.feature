Feature: Server Health Display
  As an OpenClaw operator
  I want to see system resource usage
  So I can ensure the server is healthy

  Scenario: Display CPU, memory, and disk usage
    Given the server has system monitoring tools installed
    When the server panel refreshes
    Then I should see CPU usage as a percentage
    And I should see memory usage with used/total
    And I should see disk usage with used/total

  Scenario: Color code based on thresholds
    Given memory usage is above 90%
    When the server panel renders
    Then memory should be displayed in red

  Scenario: Show gateway status
    Given the OpenClaw gateway is running
    When the server panel refreshes
    Then I should see gateway status as "running"
