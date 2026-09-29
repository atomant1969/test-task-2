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

These are covered separately — see the checklist in `docs/checklist.md` if you want the full picture.

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
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>