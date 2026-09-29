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


# =============================================================================
# Step 3: Math-Based Data Generation
# =============================================================================
# Every second, the server needs new mock data to send. This function
# calculates that data using a timer variable called `tick`, passed in
# by the caller.
#
# What it does:
# - Loops 10 times (once per signal, ID 1 through 10).
# - Applies a sine wave formula for each signal:
#       100.0 * math.sin(tick * 0.1 + i) + i * 10
#   Because `tick` changes over time and `i` (the signal ID) shifts the
#   phase, every single ID gets a unique, smooth, changing value.
#   The `+ i * 10` offset gives each signal a distinct baseline so the
#   values don't all overlap around zero.
# - Formats each line as plain text in the protocol:
#       ID=<number>;VALUE=<decimal>
#   Values are formatted to two decimal places for stable display.
# - Joins all lines with newline characters and appends a trailing
#   newline, so the payload is a well-formed block of text.
#
# Why this design:
# Using a deterministic wave (rather than random values) makes it easy
# for the test to verify that the application is refreshing correctly.
# If the display is frozen, the values will look stuck at the same point
# of the wave — an obvious visual signal.
#
# Args:
#     tick: An integer that increases by 1 on every send cycle.
#
# Returns:
#     A string containing all 10 signals, one per line, ready to be
#     encoded and sent over the socket.
# =============================================================================
def generate_signals(tick: int) -> str:
    lines = []
    for i in range(1, SIGNAL_COUNT + 1):
        # Phase-shifted sine wave per signal, amplitude 100, offset by ID
        value = 100.0 * math.sin(tick * 0.1 + i) + i * 10
        lines.append(f"ID={i};VALUE={value:.2f}")
    return "\n".join(lines) + "\n"


# =============================================================================
# Step 4: The Client Delivery Loop
# =============================================================================
# This function runs inside a background worker thread — one thread per
# connected client. It is responsible for continuously pushing fresh
# signal data to that specific client until the client disconnects.
#
# What it does:
# - Prints a connection message with the client's address, so the
#   operator can see who connected and when.
# - Initialises a local `tick` counter starting at 0. This counter
#   drives the sine wave progression for this client.
# - Enters an infinite loop that:
#       1. Calls generate_signals(tick) to build the current payload.
#       2. Encodes the payload to UTF-8 bytes and sends it over the
#          socket using conn.sendall(), which guarantees the whole
#          payload is transmitted before returning.
#       3. Increments `tick` so the next payload has progressed one
#          step further along the wave.
#       4. Sleeps for SEND_INTERVAL seconds (1.0s) before repeating.
#
# Why this runs in a thread:
# If the server handled a client directly in the main loop, it would
# freeze for everyone else while sending to one client. Running each
# client in its own thread allows multiple simultaneous connections.
#
# Step 5: Disconnection Handling & Cleanup
# Network connections can break unexpectedly. If the client closes
# their program abruptly, Python throws BrokenPipeError or
# ConnectionResetError. Both are caught here, printed as a clean
# disconnection message, and the thread exits without crashing the
# server. The `finally` block guarantees conn.close() is called no
# matter what — freeing the socket resource and avoiding leaks.
#
# Args:
#     conn: The socket object representing the connection to this
#           specific client.
#     addr: The client's network address (IP, port) for logging.
# =============================================================================
def handle_client(conn: socket.socket, addr):
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


# =============================================================================
# Step 1: Server Setup and Initialization
# Step 2: The Infinite Connection Loop
# =============================================================================
# This is the entry point of the service. It prepares the network
# socket, starts listening for clients, and accepts connections
# forever, spawning a worker thread for each one.
#
# Step 1 — Setup:
# - Creates a socket with:
#       AF_INET      = IPv4 addressing
#       SOCK_STREAM  = TCP (reliable, ordered, stream-based transport)
# - Sets SO_REUSEADDR so the port can be reused immediately after a
#   restart, without waiting for the OS to release the previous
#   binding (avoids "address already in use" errors during dev).
# - Binds the socket to HOST (127.0.0.1) and PORT (2001). This means
#   the service only accepts connections from the local machine,
#   which is appropriate for a test simulator.
# - Calls listen(5), which starts accepting connections and allows
#   up to 5 pending connections to queue while the server is busy.
#
# Step 2 — Connection loop:
# - Enters a `while True` loop that runs forever.
# - Calls server.accept(), which blocks until a client connects.
#   When a client arrives, accept() returns:
#       conn = a new socket object for this specific client
#       addr = the client's (IP, port) tuple
# - Spawns a daemon thread running handle_client(conn, addr) so this
#   client can be served without blocking the main loop. Multiple
#   clients are served concurrently.
# - Daemon threads are used so that if the main process exits
#   (e.g. Ctrl+C), the worker threads are not left hanging.
#
# Clean shutdown:
# - KeyboardInterrupt (Ctrl+C) is caught to print a clean shutdown
#   message instead of a stack trace.
# - The `finally` block closes the listening socket, releasing the
#   port.
#
# Usage:
#     python simulator/service_simulator.py
# =============================================================================
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
