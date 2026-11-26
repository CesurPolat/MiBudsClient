"""Run application cleanup once, including partially initialized sessions."""

import threading


class ApplicationShutdown:
    def __init__(self):
        self.started = threading.Event()
        self._lock = threading.RLock()
        self._callbacks = []

    def register(self, name, callback):
        with self._lock:
            if self.started.is_set():
                callback()
            else:
                self._callbacks.append((name, callback))

    def stop(self):
        # Concurrent callers wait for the same cleanup to finish.
        with self._lock:
            if self.started.is_set():
                return
            self.started.set()
            for name, callback in reversed(self._callbacks):
                try:
                    callback()
                except Exception as error:
                    print(f"Shutdown cleanup failed ({name}): {error}")
            self._callbacks.clear()
