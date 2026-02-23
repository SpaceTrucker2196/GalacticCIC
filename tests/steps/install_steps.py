"""Step definitions for Installation feature."""

import importlib
import os

from behave import given, when, then


@given("galactic_cic is installed")
def step_installed(context):
    context.test_data["installed"] = True


@when("I import the package")
def step_import_package(context):
    try:
        context.test_data["module"] = importlib.import_module("galactic_cic")
        context.test_data["import_error"] = None
    except ImportError as e:
        context.test_data["module"] = None
        context.test_data["import_error"] = str(e)


@then("it should load without errors")
def step_no_import_errors(context):
    assert context.test_data["import_error"] is None, (
        f"Import failed: {context.test_data['import_error']}"
    )
    assert context.test_data["module"] is not None


@when("I check the module entry point")
def step_check_entry(context):
    try:
        app_mod = importlib.import_module("galactic_cic.app")
        context.test_data["app_module"] = app_mod
    except ImportError as e:
        context.test_data["app_module"] = None
        context.test_data["import_error"] = str(e)


@then("it should have a main function")
def step_has_main(context):
    app_mod = context.test_data.get("app_module")
    assert app_mod is not None, "Could not import galactic_cic.app"
    assert hasattr(app_mod, "main"), "galactic_cic.app has no 'main' function"
    assert callable(app_mod.main), "galactic_cic.app.main is not callable"


@when("I check for required packages")
def step_check_packages(context):
    context.test_data["packages_checked"] = True


@given("the requirements file exists")
def step_requirements_exist(context):
    req_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "requirements.txt"
    )
    assert os.path.exists(req_path), f"requirements.txt not found at {req_path}"


@then("textual should be available")
def step_textual_available(context):
    # Replaced by curses (stdlib) — always available
    import curses  # noqa: F401


@then("rich should be available")
def step_rich_available(context):
    # No longer needed — curses handles all rendering
    # Check that our StyledText replacement exists instead
    from galactic_cic.panels.base import StyledText  # noqa: F401
