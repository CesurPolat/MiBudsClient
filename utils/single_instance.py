"""Utility for ensuring only a single instance of the application is running."""

import socket
import sys
import threading

SINGLE_INSTANCE_PORT = 65432

def check_for_existing_instance():
    """
    Checks if another instance is running. If so, sends a 'focus' message
    to it and exits the current process.
    """
    try:
        # Try to bind to the port to see if it's free
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.bind(('127.0.0.1', SINGLE_INSTANCE_PORT))
        test_socket.close()
    except socket.error:
        # Port is busy, likely another instance is running
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(('127.0.0.1', SINGLE_INSTANCE_PORT))
            client.sendall(b"focus")
            client.close()
        except Exception:
            pass  # Fail silently if the other instance is not ready
        sys.exit(0)  # Exit the new instance

def start_instance_listener(window_manager):
    """
    Starts a thread that listens for 'focus' messages from new instances.
    """
    def listen_thread():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow address reuse to avoid "Address already in use" errors on restart
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', SINGLE_INSTANCE_PORT))
            s.listen(1)
            while True:
                conn, addr = s.accept()
                data = conn.recv(1024)
                if data == b"focus":
                    if window_manager:
                        window_manager.show()
                conn.close()
        except Exception:
            pass # Fail silently

    threading.Thread(target=listen_thread, daemon=True).start()
