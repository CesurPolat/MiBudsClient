"""Watch the application holding automatic low latency mode."""

import subprocess
import sys
import threading

from utils.app.pubsub_topics import PubSubTopic


def is_process_running(app_id: str) -> bool:
    app_name = (app_id or "").strip().lower()
    if not app_name:
        return False

    try:
        if sys.platform.startswith("win"):
            startupinfo = None
            creationflags = 0
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {app_name}"],
                capture_output=True,
                text=True,
                startupinfo=startupinfo,
                creationflags=creationflags,
                check=False,
            )
            output = (result.stdout or "").lower()
            return app_name in output and "no tasks are running" not in output

        if sys.platform.startswith("linux"):
            result = subprocess.run(
                ["pgrep", "-f", app_name],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and bool((result.stdout or "").strip())
    except Exception:
        return False

    return False


class HoldWatcher:
    def __init__(self, *, state, lock, stopped, check_process, publish):
        self._state = state
        self._lock = lock
        self._stopped = stopped
        self._check_process = check_process
        self._publish = publish

    def _active_app(self):
        if self._state["selected_mode"] == "auto" and self._state["hold_until_app_close_enabled"]:
            return self._state["latency_hold_app_id"]
        return ""

    def clear(self) -> None:
        self._state["latency_hold_app_id"] = ""

    def set_app(self, app_id: str) -> None:
        app_id = (app_id or "").strip().lower()
        if app_id and self._state["hold_until_app_close_enabled"]:
            self._state["latency_hold_app_id"] = app_id
            self.start()

    def start(self):
        with self._lock:
            if self._stopped.is_set() or self._state["hold_watcher_running"] or not self._active_app():
                return
            self._state["hold_watcher_running"] = True
            try:
                threading.Thread(target=self._watch, daemon=True).start()
            except Exception:
                self._state["hold_watcher_running"] = False
                raise

    def _watch(self):
        try:
            while not self._stopped.is_set():
                with self._lock:
                    app_id = self._active_app()
                if not app_id:
                    return

                if not self._check_process(app_id):
                    with self._lock:
                        if self._stopped.is_set():
                            return
                        if self._active_app() != app_id:
                            continue
                        self._publish({"type": PubSubTopic.AUTO_HOLD_RELEASED.value, "app_id": app_id})
                    return

                if self._stopped.wait(2):
                    return
        finally:
            with self._lock:
                self._state["hold_watcher_running"] = False
