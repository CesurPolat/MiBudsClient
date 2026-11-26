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

_reserved_socket = None
_reservation_lock = threading.Lock()


def reserve_instance_port():
    """Hold the instance port throughout startup, before the window is ready."""
    global _reserved_socket
    with _reservation_lock:
        if _reserved_socket is not None:
            return _reserved_socket
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            listener.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
            listener.listen(8)
        except OSError:
            listener.close()
            # Another startup may have won after check_for_existing_instance().
            try:
                with socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT), timeout=1) as client:
                    client.sendall(b"focus")
            except OSError:
                pass
            sys.exit(0)
        _reserved_socket = listener
        return listener


def release_instance_port():
    """Release the reservation once the application has shut down."""
    global _reserved_socket
    with _reservation_lock:
        if _reserved_socket is not None:
            try:
                _reserved_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            _reserved_socket.close()
            _reserved_socket = None


def start_instance_listener(window_manager):
    """Consume focus requests queued on the socket reserved during startup."""
    listener = reserve_instance_port()

    def listen_thread():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(1)
                try:
                    data = conn.recv(1024)
                except OSError:
                    continue
                if data == b"focus" and window_manager:
                    window_manager.show()

    threading.Thread(target=listen_thread, daemon=True).start()
