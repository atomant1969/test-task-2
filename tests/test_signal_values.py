"""
Automated test for the signal management desktop application.

Scenario: verify that the signal values displayed in the application
match the data received from the simulator service over TCP.

Dependencies:
    pip install pytest pywinauto
    (pywinauto — for desktop UI automation; for Linux/macOS replace it with
     an equivalent tool such as dogtail or pyautogui)
"""

import socket
import time
import re
import pytest
from pywinauto.application import Application


# --- Configuration ---
SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 2001
APP_PATH = r"C:\Path\To\SignalApp.exe"   # path to the application executable
EXPECTED_SIGNAL_COUNT = 10


# =============================================================================
# EXECUTION FLOW — how the script runs
# =============================================================================
#
# When you run `pytest`, the following sequence happens:
#
# 1. pytest loads this file and collects the test functions.
#    It finds `test_signal_values_match_service`.
#
# 2. pytest sees that the test function requires the fixture `app`.
#    Before running the test, pytest calls the `app` fixture.
#
# 3. Inside `app` (fixture):
#    a. The application is launched from APP_PATH.
#    b. The main window is located by title pattern.
#    c. The "Connect" button is clicked — the application opens a TCP
#       connection to the simulator service and starts receiving data.
#    d. A short pause lets the table populate.
#    e. `yield` hands the window object back to pytest, which then
#       passes it into the test function as the `app` argument.
#
# 4. `test_signal_values_match_service(app)` runs:
#    a. Calls `read_reference_signals(SERVICE_HOST, SERVICE_PORT)` —
#       opens its own TCP connection to the service and reads the
#       reference values directly from the source.
#    b. Asserts the service returned the expected number of signals.
#    c. Clicks "Refresh" in the application.
#    d. Calls `read_app_signals(app)` — reads the table from the
#       application window.
#    e. Asserts the table contains the expected number of signals.
#    f. Compares each ID and value; collects any mismatches.
#    g. Asserts there are no mismatches.
#
# 5. After the test finishes (pass or fail), execution returns to the
#    `app` fixture, right after the `yield`.
#    The application window is closed, and a short pause allows the
#    process to shut down cleanly.
#
# 6. pytest reports the result.
#
# Method call order at runtime:
#   pytest
#     -> app()                  [fixture setup]
#         -> Application.start()
#         -> window.click("Connect")
#     -> test_signal_values_match_service(app)
#         -> read_reference_signals()
#         -> window.click("Refresh")
#         -> read_app_signals()
#     -> app()                  [fixture teardown]
#         -> window.close()
#
# =============================================================================


# =============================================================================
# STEP 1 (of the test) — read reference data from the simulator service
# =============================================================================
# Called from: test_signal_values_match_service(), as the first step.
# Calls: nothing else in this file — it uses socket and re directly.
#
# What it does in the flow:
# This function is the source of truth for the test. Before we can check
# whether the application displays correct values, we need to know what
# the correct values actually are. So we open our own TCP connection to
# the service (the same service the application is connected to) and
# read what it is sending right now.
#
# How it works:
# - Opens a TCP connection to host:port.
# - Sets a timeout so the function does not hang.
# - Reads data until it has all expected signals or the timeout expires.
# - Parses lines matching the protocol: ID=<int>;VALUE=<float>.
# - Returns a list of {"id": int, "value": float} dictionaries.
#
# If the service format changes (JSON, binary, fixed-width), the parser
# must be updated. Here we assume the simple text protocol used by the
# simulator.
#
# Args:
#     host:    service address (default 127.0.0.1)
#     port:    service port (default 2001)
#     timeout: maximum wait time in seconds
#
# Returns:
#     List of {"id": int, "value": float} reference values.
# =============================================================================
def read_reference_signals(host, port, timeout=5):
    signals = []
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        buffer = b""
        # Keep reading until we have all signals or the timeout expires
        deadline = time.time() + timeout
        while len(signals) < EXPECTED_SIGNAL_COUNT and time.time() < deadline:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
            except socket.timeout:
                break

        # Parse the received lines
        text = buffer.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            match = re.match(r"ID=(\d+);VALUE=([\d.\-]+)", line.strip())
            if match:
                signals.append({
                    "id": int(match.group(1)),
                    "value": float(match.group(2)),
                })
    return signals


# =============================================================================
# STEP 4 (of the test) — read signal values from the application's table
# =============================================================================
# Called from: test_signal_values_match_service(), as the fourth step
# (after the "Refresh" click).
# Calls: nothing else in this file — it walks the UI tree via pywinauto.
#
# What it does in the flow:
# This handles the second half of the comparison. We have the reference
# values from the service (Step 1). Now we read what is actually shown
# in the application's table — this is what we compare against.
#
# How it works:
# - Finds the table control in the main window.
# - Gets all rows (DataItem controls).
# - For each row, reads the ID (first cell) and value (third cell).
# - Collects everything into a dictionary {id: value}.
#
# Why a dictionary:
# Comparison is by signal ID, not row order. A dictionary allows fast
# lookup by ID and is independent of how the application sorts rows.
#
# If the real application has a different column order or control types,
# update the indexes and control_type values. Use Inspect.exe or
# Accessibility Insights to find the correct names.
#
# Args:
#     window: the main application window object (from the `app` fixture).
#
# Returns:
#     Dictionary {signal_id: value}, e.g. {1: 42.51, 2: -17.32, ...}.
# =============================================================================
def read_app_signals(window):
    app_signals = {}
    table = window.child_window(control_type="Table")  # verify control_type

    # Get all rows of the table
    rows = table.children(control_type="DataItem")
    for row in rows:
        cells = row.children()
        if len(cells) < 3:
            continue
        try:
            signal_id = int(cells[0].window_text().strip())   # ID column
            value = float(cells[2].window_text().strip())     # value column
            app_signals[signal_id] = value
        except (ValueError, AttributeError):
            # Skip rows that could not be parsed
            continue
    return app_signals


# =============================================================================
# STEP 0 (fixture) — launch the application and prepare the test
# =============================================================================
# Called by: pytest, automatically, before the test function runs.
# Calls: pywinauto (Application.start, window, child_window.click, close).
#
# Where it sits in the flow:
# This runs first, before `test_signal_values_match_service`. It prepares
# the environment: launches the application and connects it to the
# service, so that when the test starts, the table is already populated.
#
# Step by step:
# - Launches the application from APP_PATH using pywinauto (UIA backend).
# - Locates the main window by title pattern.
# - Waits until the window is ready.
# - Clicks "Connect" so the application starts receiving data.
# - Pauses to let the table populate.
# - `yield` hands the window object to the test function.
#   Everything after the `yield` is teardown.
# - After the test completes: closes the window and pauses briefly.
#
# Why scope="module":
# The application launches once per test module, not per test. New tests
# added to this file reuse the same window — faster and lighter on the
# system.
#
# Yields:
#     The main application window object — passed to the test as `app`.
# =============================================================================
@pytest.fixture(scope="module")
def app():
    application = Application(backend="uia").start(APP_PATH)
    main_window = application.window(title_re=".*Signal.*")  # verify window title
    main_window.wait("ready", timeout=10)

    # Click "Connect"
    main_window.child_window(title="Connect", control_type="Button").click()
    time.sleep(2)  # allow time for the connection and initial data load

    yield main_window

    # Close the application after the tests
    main_window.close()
    time.sleep(1)


# =============================================================================
# TEST ENTRY POINT — critical scenario: values match the service
# =============================================================================
# Called by: pytest (as the test itself).
# Calls: read_reference_signals(), then read_app_signals(), using the
#        window provided by the `app` fixture.
#
# Where it sits in the flow:
# This is the main test. It runs after the `app` fixture has set up the
# environment. Steps 1 through 4 below match the "EXECUTION FLOW" section
# at the top of this file.
#
# Test steps:
# 1. Retrieve reference values from the service (read_reference_signals).
# 2. Assert the service returned all expected signals.
# 3. Click "Refresh" in the application.
# 4. Read values from the application table (read_app_signals).
# 5. Assert the table contains all expected signals.
# 6. Compare values by ID with a tolerance of 0.01 (for display rounding).
# 7. Assert there are no mismatches.
#
# Why this scenario is critical:
# The application is part of a distributed control system. If an operator
# sees incorrect values, they make decisions based on false data. So a
# mismatch is a serious defect, not a cosmetic one.
#
# Args:
#     app: the main application window object, provided by the fixture.
# =============================================================================
def test_signal_values_match_service(app):
    # Step 1: reference data from the service
    reference_signals = read_reference_signals(SERVICE_HOST, SERVICE_PORT)

    # Verify the service returned data at all — otherwise the test is meaningless
    assert len(reference_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Simulator service returned {len(reference_signals)} signals, "
        f"expected {EXPECTED_SIGNAL_COUNT}"
    )

    # Step 3: request a refresh in the application
    app.child_window(title="Refresh", control_type="Button").click()
    time.sleep(2)  # allow the application to fetch and display new values

    # Step 4: read values from the application's table
    app_signals = read_app_signals(app)

    # Step 5: verify the table has the expected number of signals
    assert len(app_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Application displays {len(app_signals)} signals, "
        f"expected {EXPECTED_SIGNAL_COUNT}"
    )

    # Step 6: compare
    mismatches = []
    for ref in reference_signals:
        signal_id = ref["id"]
        expected_value = ref["value"]

        assert signal_id in app_signals, (
            f"Signal ID={signal_id} is missing from the application's table"
        )

        actual_value = app_signals[signal_id]

        # Tolerance for rounding: floating-point values may be displayed
        # with less precision than they arrive over the network
        if abs(actual_value - expected_value) > 0.01:
            mismatches.append(
                f"ID={signal_id}: application shows {actual_value}, "
                f"service sent {expected_value}"
            )

    # Step 7: if there are mismatches — fail with a readable list
    assert not mismatches, (
        "Signal values in the application do not match the data from the service:\n"
        + "\n".join(mismatches)
    )
