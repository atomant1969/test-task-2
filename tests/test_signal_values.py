"""
Automated test for the signal management desktop application.

Scenario: verify that the signal values displayed in the application
match the data received from the simulator service over TCP.

Test logic:
1. Start the simulator service (or use one already running on port 2001).
2. Connect to it directly as a client and retrieve the reference data.
3. Connect the application to the service and click "Refresh".
4. Read the values from the application's table.
5. Compare: the values in the application must match the reference data.

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
# Read reference data from the simulator service
# =============================================================================
# This function is the source of truth for the entire test. It connects
# to the simulator service directly, as a regular TCP client, and reads
# the signal values the service is currently sending.
#
# Why this matters:
# The test does not verify that the application "agrees with itself" —
# it verifies that the data in the application matches the real data
# from the source. So we first retrieve the reference values from the
# service, then compare them with what the application displays.
#
# What it does:
# - Opens a TCP connection to the service at host:port.
# - Sets a timeout so the function does not hang if the service is
#   unreachable or responds slowly.
# - Reads data from the socket in a loop until it has all expected
#   signals (EXPECTED_SIGNAL_COUNT) or until the timeout expires.
# - Parses the received text with a regex matching the format
#   ID=<int>;VALUE=<float> — the simulator's protocol.
# - Returns a list of dictionaries:
#       [{"id": 1, "value": 42.51}, {"id": 2, "value": -17.32}, ...]
#
# Important:
# If the service uses a different data format (JSON, binary, fixed-width
# packets), the parser must be adapted. Here we assume a simple text
# protocol.
#
# Args:
#     host:    service address (default 127.0.0.1)
#     port:    service port (default 2001)
#     timeout: maximum wait time for data, in seconds
#
# Returns:
#     A list of {"id": int, "value": float} dictionaries with reference values.
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
# Read signal values from the application's table
# =============================================================================
# This function handles the second half of the comparison: it reads what
# is actually displayed in the main window's signal table.
#
# What it does:
# - Finds the signal table in the main window via pywinauto
#   (control_type="Table" — the control type needs to be verified against
#   the real application using Inspect.exe).
# - Gets all rows of the table (control_type="DataItem").
# - For each row, reads the cells and extracts:
#       - Signal ID (first column, converted to int)
#       - Signal value (third column, converted to float)
# - Collects everything into a dictionary of the form {id: value}.
#
# Why a dictionary, not a list:
# The comparison is by signal ID, not by row order in the table. A
# dictionary allows fast lookup by ID and does not depend on how the
# application sorts its rows.
#
# Important:
# Column names and their order depend on the application's implementation.
# If the structure is different (for example, the value is in the second
# column instead of the third), the indexes must be adjusted. Rows that
# cannot be parsed (empty rows, headers) are silently skipped.
#
# Args:
#     window: the main application window object (pywinauto WindowSpecification).
#
# Returns:
#     A dictionary {signal_id: value}, e.g. {1: 42.51, 2: -17.32, ...}.
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
# Fixture: launch and shut down the application
# =============================================================================
# A pytest fixture that prepares the test environment: launches the
# application, waits until it is ready, connects to the service, and
# hands control to the test. After the test completes, it closes the
# application.
#
# Step by step:
# - Launches the application from APP_PATH via pywinauto with
#   backend="uia" (UIA is the modern Windows automation interface, it
#   works with WPF, WinForms, UWP, and Qt applications).
# - Finds the main window by title pattern (title_re=".*Signal.*" —
#   this needs to be adjusted to the real window title).
# - Waits for the window to become ready for interaction (wait("ready")).
# - Clicks the "Connect" button — the application establishes a TCP
#   connection with the simulator service.
# - Pauses to let the application receive the first batch of data and
#   populate the table.
# - Yields the window to the test. Everything after the yield runs
#   after the test completes.
# - Closes the application and pauses briefly so the process shuts
#   down cleanly.
#
# Why scope="module":
# The application is launched once for the whole test module, not once
# per test. This is faster and puts less load on the system — if new
# tests are added to the file, they reuse the same window.
#
# Important:
# The window title and button names may differ in the real application.
# Verify them through Inspect.exe or Accessibility Insights and update
# this fixture accordingly.
#
# Yields:
#     The main application window object — for use in the tests.
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
# Critical scenario: values in the application match the data from the service
# =============================================================================
# This is the test itself — it verifies the core promise of the product:
# the signal values displayed in the application must match what is
# actually coming from the service.
#
# Why this is critical:
# The application is part of a distributed control system. If an operator
# sees incorrect values, they make decisions based on false data. So a
# mismatch is not a cosmetic bug — it is a serious defect.
#
# Test steps:
# 1. Retrieve reference values from the service directly (as a TCP client).
#    This is what the service is sending right now — the source of truth.
# 2. Verify that the service returned all expected signals. If not, the
#    test fails immediately, because there is nothing to compare against.
# 3. Click "Refresh" in the application — it requests fresh data and
#    redraws the table.
# 4. Read the values from the application's table.
# 5. Verify that the table contains the expected number of signals.
# 6. Compare values by each ID. A tolerance of 0.01 is applied — because
#    values may be rounded for display.
# 7. If there are mismatches, the test fails with a readable list:
#    which ID, what the application shows, what the service sent.
#
# Why assertions have detailed messages:
# When the test fails, it is important to see immediately what did not
# match — not just "AssertionError". This saves time during debugging
# and makes the test a useful tool, not a formality.
#
# Args:
#     app: the main application window object provided by the fixture.
# =============================================================================
def test_signal_values_match_service(app):
    # Step 1: reference data from the service
    reference_signals = read_reference_signals(SERVICE_HOST, SERVICE_PORT)

    # Verify the service returned data at all — otherwise the test is meaningless
    assert len(reference_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Simulator service returned {len(reference_signals)} signals, "
        f"expected {EXPECTED_SIGNAL_COUNT}"
    )

    # Step 2: request a refresh in the application
    app.child_window(title="Refresh", control_type="Button").click()
    time.sleep(2)  # allow the application to fetch and display new values

    # Step 3: read values from the application's table
    app_signals = read_app_signals(app)

    # Step 4: compare
    assert len(app_signals) == EXPECTED_SIGNAL_COUNT, (
        f"Application displays {len(app_signals)} signals, "
        f"expected {EXPECTED_SIGNAL_COUNT}"
    )

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

    # If there are mismatches — the test fails with a readable list
    assert not mismatches, (
        "Signal values in the application do not match the data from the service:\n"
        + "\n".join(mismatches)
    )
