"""Own the device-confirmed latency state and the active session's display data."""

import threading

from utils.app.i18n import error_message, message as m


class LatencyDevice:
    def __init__(self, get_controller, stopped, state):
        self._get_controller = get_controller
        self._stopped = stopped
        self._state = state
        self._capabilities = None
        self._read_session = None
        self._read_lock = threading.Lock()
        self._error = None
        self._activation_app = ""
        self._activation_session = None

    def set_capabilities(self, capabilities) -> bool:
        if capabilities == self._capabilities:
            return False
        self._capabilities = capabilities
        self.update_activation("")
        self.invalidate()
        self.clear_error()
        return True

    def invalidate(self) -> None:
        self._state["effective_low_latency"] = None

    def clear_error(self) -> None:
        self._error = None

    def update_activation(self, app_id: str, controller=None) -> bool:
        if controller is not None and app_id and self._state["effective_low_latency"] is True:
            session = (controller, controller.gesture_session)
        else:
            app_id, session = "", None
        if (app_id, session) == (self._activation_app, self._activation_session):
            return False
        self._activation_app, self._activation_session = app_id, session
        return True

    def sync(self):
        controller = self._get_controller()
        self._state["effective_low_latency"] = controller.latency_state if controller is not None else None
        return controller

    def display_state(self) -> dict:
        controller = self.sync()
        mode = self._state["selected_mode"]
        enabled = self._state["effective_low_latency"]
        activation_app = ""
        if (controller is not None and mode == "auto" and enabled is True and not self._error
                and self._activation_session == (controller, controller.gesture_session)):
            activation_app = self._activation_app
        return {"mode": mode, "enabled": enabled, "error": self._error, "activation_app": activation_app}

    def refresh(self, on_read):
        """Request one read for each ready connection and capability set."""
        controller = self._get_controller()
        if self._stopped.is_set() or controller is None or not controller.session_ready:
            return
        capabilities = controller.capabilities
        if not capabilities.supports("latency"):
            return
        session = controller.gesture_session
        key = (controller, session, capabilities)
        with self._read_lock:
            if key == self._read_session:
                return
            self._read_session = key

        def read():
            try:
                controller.request_latency_state(session=session)
            except (OSError, ValueError):
                pass  # Unreadable configuration stays unknown.
            if (not self._stopped.is_set() and controller is self._get_controller()
                    and session == controller.gesture_session):
                on_read("device_read")

        try:
            threading.Thread(target=read, daemon=True).start()
        except Exception:
            with self._read_lock:
                if self._read_session == key:
                    self._read_session = None
            raise

    def set_enabled(self, controller, enabled: bool) -> tuple[bool, str]:
        if controller is None:
            success, message = False, m("latency.unavailable")
        else:
            try:
                success, message = controller.send_command("low" if enabled else "std")
            except Exception as exc:
                success, message = False, m("latency.failed", details=error_message(exc))
        self.sync()
        self._error = None if success else message
        return success, message
