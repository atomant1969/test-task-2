# Signal App QA — Automated Test

Automated test suite for a desktop signal-management application that is part of a distributed control system. The application receives signal values from a remote service over a TCP socket and displays them in a table (ID, name, value, quality, timestamp).

This repository contains a pytest-based test that verifies the most critical scenario: **the values displayed in the application match the data sent by the service.**

---

## Purpose

The application is part of a distributed control system. If an operator sees incorrect signal values, they make decisions based on false data. This is not a cosmetic bug — it can cause real damage.

The test checks the core promise of the product:

1. The service-simulator sends 10 signals with changing values over TCP (port 2001).
2. The application connects to the service and displays the signals in a table.
3. **The test compares the values shown in the application against the values received directly from the service.**

Any mismatch is treated as a defect.

### What the test does NOT cover

This is a focused test, not a full regression suite. It does not check:

- UI layout, styling, or responsiveness
- Connection loss and reconnection behaviour
- Quality field semantics (good / bad / uncertain)
- Timestamp accuracy
- Invalid or malformed data handling
- Performance under rapid refresh

These are covered separately — see the checklist in `docs/checklist.md`.

---

## Requirements

- **Python 3.9+**
- **Windows** (the test uses `pywinauto` with the UIA backend)
- A running instance of the **service-simulator** on `127.0.0.1:2001`
- The **desktop application** installed locally
- The application must be **connectable via UI automation** (standard Win32/UIA controls — not custom-drawn)

### Dependencies

| Package     | Purpose                                      |
|-------------|----------------------------------------------|
| `pytest`    | Test runner                                   |
| `pywinauto` | Desktop UI automation (Windows, UIA backend)  |

For Linux or macOS, `pywinauto` will not work. Replace the UI layer with `dogtail` (Linux) or `pyautogui` / accessibility APIs (macOS). The service-side logic is platform-independent.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/atomant1969/test-task-2.git
cd test-task-2
```

### 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (cmd):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install pytest pywinauto
```

---

## Setup

### 1. Start the service-simulator

The simulator must be running on `127.0.0.1:2001` before the test starts:

```bash
python simulator/service_simulator.py
```

Confirm the port is open:

```bash
# Windows
netstat -an | findstr 2001

# Linux / macOS
lsof -i :2001
```

### 2. Configure the test

Open `tests/test_signal_values.py` and update the configuration block at the top:

```python
SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 2001
APP_PATH = r"C:\Path\To\SignalApp.exe"   # <-- update this
EXPECTED_SIGNAL_COUNT = 10
```

You will also likely need to adjust the UI control names — they depend on how the application is built. Use **Inspect.exe** (comes with Windows SDK) or **Accessibility Insights** to find the correct `control_type`, window titles, and button names.

Key places to check:

- `app.window(title_re=".*Signal.*")` — the main window title pattern
- `child_window(title="Connect", control_type="Button")` — the Connect button
- `child_window(title="Refresh", control_type="Button")` — the Refresh button
- `child_window(control_type="Table")` — the signals table

### 3. Check the service data format

The test parses the service response as:

```
ID=1;VALUE=42.5
ID=2;VALUE=17.3
...
```

If your simulator uses a different format (JSON, binary, fixed-width packets), update the parser in `read_reference_signals()`.

---

## Usage

### Run all tests

```bash
pytest -v
```

### Run only the critical scenario test

```bash
pytest tests/test_signal_values.py::test_signal_values_match_service -v
```

### Run with output printed to console

```bash
pytest -v -s
```

### Run with a longer timeout

```bash
pytest -v --timeout=60
```

*(Requires `pytest-timeout`: `pip install pytest-timeout`)*

### Expected output on success

```
tests/test_signal_values.py::test_signal_values_match_service PASSED
```

### Expected output on failure

```
AssertionError: Signal values in the application do not match the data from the service:
ID=3: application shows 12.4, service sent 12.7
ID=7: application shows 88.1, service sent 88.9
```

---

## Project structure

```
.
├── README.md
├── README_ENG.md
├── requirements.txt
├── tests/
│   └── test_signal_values.py    # Main test file
├── docs/
│   ├── checklist.md             # Full QA checklist (15 items)
│   └── bug_report_template.md   # Bug report format + examples
└── simulator/
    └── service_simulator.py     # Local simulator for development
```

---

## How the test works

1. **Reads reference data directly from the service.**
   Opens a TCP connection to `127.0.0.1:2001`, reads the raw signal data, and parses it into `{id: value}` pairs. This is the source of truth.

2. **Connects the application.**
   Launches the desktop app via `pywinauto`, waits for the main window, and clicks "Connect".

3. **Requests a refresh.**
   Clicks "Refresh" and waits for the table to update.

4. **Reads values from the application's table.**
   Walks through the table rows and extracts `{id: value}`.

5. **Compares and asserts.**
   Every signal ID from the service must exist in the app with a matching value. A tolerance of `0.01` is applied to account for display rounding. Any mismatch fails the test with a readable list.

---

## Troubleshooting

**`pywinauto.ElementNotFoundError`**
The UI control names in the test don't match the actual application. Use Inspect.exe to find the correct `control_type` and window titles, then update the selectors.

**`ConnectionRefusedError` when reading reference signals**
The service-simulator isn't running on port 2001. Start it first.

**`AssertionError: Service-simulator returned N signals, expected 10`**
Either the simulator isn't sending all 10 signals, or the parser doesn't match the actual data format.

**Test hangs on application start**
The app may take longer than the 10-second timeout to open, or the window title pattern is wrong.

**Values mismatch by a tiny amount (e.g. 0.001)**
Floating-point rounding. Widen the tolerance or check whether the app truncates values differently than expected.

---

## Notes on portability

- The **service-side logic** (reading reference signals) works on any OS with Python.
- The **UI layer** is Windows-only because of `pywinauto`.

---

## License

Internal / project-specific. Add a license if you intend to publish.