# QA Checklist — Signal Management Desktop Application

Manual test checklist for the desktop application that displays signals received from a remote service over a TCP socket.

**Scope:** functional testing of the main window, connection handling, data display, and error behaviour.

**Out of scope:** performance under load, long-running stability, security testing.

---

## Checklist

### 1. Application launch
- [ ] Application starts without errors; the main window opens and renders correctly.
- [ ] All UI elements are present: signals table, "Connect" button, "Refresh" button.
- [ ] Table columns are correctly labelled: ID, Name, Value, Quality, Timestamp.

### 2. Connection handling
- [ ] Clicking "Connect" establishes a TCP connection to the service on port 2001.
- [ ] If the service is unavailable, the application shows a clear error message and does not crash or freeze.
- [ ] Clicking "Connect" again while already connected does not create duplicate connections.
- [ ] Connection status is visible to the user (connected / disconnected indicator or message).

### 3. Initial data load
- [ ] After connecting, the signals table populates with all 10 signals.
- [ ] Each row contains valid data in all five columns — no empty or placeholder values.
- [ ] Signal IDs and names match what the service sends.

### 4. Data refresh
- [ ] Clicking "Refresh" updates the signal values in the table.
- [ ] Values in the table match the data sent by the service simulator (sine wave / random values).
- [ ] The Timestamp column updates with each refresh.
- [ ] The Quality column reflects signal reliability (good / bad / uncertain) and changes when the signal degrades.

### 5. Connection loss and recovery
- [ ] When the connection drops, the application handles it gracefully — shows status, does not freeze.
- [ ] When the service comes back, the application reconnects and resumes receiving data.
- [ ] Values stop updating during the outage (no stale data presented as fresh).

### 6. Error handling
- [ ] Repeated rapid clicks on "Refresh" do not freeze the application or duplicate requests.
- [ ] If the service sends malformed or corrupted data, the application does not crash and logs the issue.
- [ ] Closing the application terminates the connection cleanly — no orphaned process remains.

---

## Priority notes

**Most critical: data correctness (section 4).**

The application is part of a distributed control system. If an operator sees incorrect signal values, they make decisions based on false data. This is not a cosmetic issue — it can cause real damage. The values displayed in the application must match the values received from the service, at all times.

**Second most critical: connection loss (section 5).**

A frozen application in a control system is more dangerous than one that closes with an error. If the connection drops, the operator needs to know immediately and see that the data is stale — not be shown a frozen screen that looks live.

**Everything else — important, but secondary.**

Launch, layout, and error messages matter for usability, but they don't threaten the correctness of the system's output.

---

## Test data reference

| Parameter | Value |
|---|---|
| Service host | `127.0.0.1` |
| Service port | `2001` |
| Signal count | `10` |
| Data format | `ID=<int>;VALUE=<float>` per line |
| Update interval | 1 second |

---

## Related documents

- `README.md` — setup and usage for the automated test
- `tests/test_signal_values.py` — the automated test for the critical scenario (data correctness)
- `simulator/service_simulator.py` — local service simulator used during testing