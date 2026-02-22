Feature: Keyboard Navigation
  As a user
  I want to navigate the dashboard with keyboard
  So I can interact without a mouse

  Scenario: Quit with q
    Given the dashboard is running
    When I press "q"
    Then the dashboard should exit

  Scenario: Force refresh with r
    Given the dashboard is running
    When I press "r"
    Then all panels should refresh immediately

  Scenario: Focus panel with number keys
    Given the dashboard is running
    When I press "1"
    Then the agent panel should be focused
