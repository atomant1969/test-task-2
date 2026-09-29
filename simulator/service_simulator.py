"""
Signal simulator service.

Listens on TCP port 2001 and sends 10 signals with changing values
to any connected client. Values follow a sine wave pattern so the test
can verify that the application updates them correctly.

Protocol (plain text, one signal per line):
    ID=<int>;VALUE=<float>

Example payload:
    ID=1;VALUE=42.51
    ID=2;VALUE=-17.32
    ...

Usage:
    python simulator/service_simulator.py

The service runs until interrupted (Ctrl+C).
"""

import math
import socket
import threading
import time

HOST = "127.0.0.1"
PORT = 2001
SIGNAL_COUNT = 10
SEND_INTERVAL = 1.0  # seconds between updates


def generate_signals(tick: int) -> str:
    """
    Build the payload for the current tick.

    Each signal gets a distinct sine wave so values differ from each other
    and change over time. This makes it easy to spot a display that isn't
    refreshing.
    """
    lines = []
    for i in range(1, SIGNAL_COUNT + 1):
        # Phase-shifted sine wave per signal, amplitude 100, offset by ID
        value = 100.0 * math.sin(tick * 0.1 + i) + i * 10
        lines.append(f"ID={i};VALUE={value:.2f}")
    return "\n".join(lines) + "\n"


def handle_client(conn: socket.socket, addr):
    """Send signal updates to a connected client until it disconnects."""
    print(f"[simulator] client connected: {addr}")
    tick = 0
    try:
        while True:
            payload = generate_signals(tick)
            conn.sendall(payload.encode("utf-8"))
            tick += 1
            time.sleep(SEND_INTERVAL)
    except (BrokenPipeError, ConnectionResetError):
        print(f"[simulator] client disconnected: {addr}")
    finally:
        conn.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)

    print(f"[simulator] listening on {HOST}:{PORT}")
    print(f"[simulator] sending {SIGNAL_COUNT} signals every {SEND_INTERVAL}s")
    print("[simulator] press Ctrl+C to stop")

    try:
        while True:
            conn, addr = server.accept()
            # One thread per client — the test may open more than one connection
            thread = threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            )
            thread.start()
    except KeyboardInterrupt:
        print("\n[simulator] shutting down")
    finally:
        server.close()


if __name__ == "__main__":
    main()