Feature: Historical Metrics Database
  As an OpenClaw operator
  I want metrics stored historically
  So I can see trends and tokens/hour

  Scenario: Database is created on startup
    Given the database module is available
    When I create a MetricsDB instance
    Then the database file should exist
    And the schema should be initialized

  Scenario: Record and retrieve agent metrics
    Given a fresh metrics database
    When I record agent metrics for "main" with 126000 tokens
    Then I should find the agent record in the database

  Scenario: Calculate tokens per hour
    Given a database with agent token history
    When I calculate tokens per hour
    Then the result should be greater than zero

  Scenario: Server trend arrows
    Given a database with server metrics over time
    When I calculate server trends
    Then I should see trend arrows for CPU, MEM, and DISK
