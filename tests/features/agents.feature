Feature: Agent Fleet Display
  As an OpenClaw operator
  I want to see all my agents and their status
  So I can monitor fleet health

  Scenario: Display all configured agents
    Given the OpenClaw instance has 3 agents configured
    When the CIC dashboard loads the agent panel
    Then I should see 3 agents listed
    And each agent should show name, status, and model

  Scenario: Show session counts per agent
    Given agent "main" has 5 active sessions
    When the agent panel refreshes
    Then I should see "5" sessions for agent "main"

  Scenario: Handle openclaw command failure gracefully
    Given the openclaw CLI is not available
    When the agent panel tries to refresh
    Then I should see an error message instead of agent data
    And the dashboard should not crash
