Feature: Installation
  As a user
  I want to install GalacticCIC easily
  So I can start monitoring my OpenClaw deployment

  Scenario: Package is importable
    Given galactic_cic is installed
    When I import the package
    Then it should load without errors

  Scenario: Module is runnable
    Given galactic_cic is installed
    When I check the module entry point
    Then it should have a main function

  Scenario: Dependencies are available
    Given the requirements file exists
    When I check for required packages
    Then textual should be available
    And rich should be available
