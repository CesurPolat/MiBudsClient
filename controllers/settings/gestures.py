"""Run gesture requests off the UI thread and publish versioned completions."""

import threading

from controllers.bluetooth.gestures import GestureResult


class GestureSettingsController:
    def __init__(self, controller, panel, publish):
        self._controller = controller
        self._panel = panel
        self._publish = publish

    def refresh(self):
        self._start(None)

    def assign(self, gesture_type, side, action):
        self._start((gesture_type, side, action))

    def _start(self, assignment):
        session = self._controller.gesture_session
        token = self._panel.begin("Saving and verifying assignment..." if assignment else "Reading gesture settings...")
        if token is None:
            return
        def work():
            try:
                if assignment:
                    result = self._controller.set_gesture_assignment(*assignment, session=session)
                else:
                    result = self._controller.request_gesture_settings(session=session)
                capabilities = self._controller.gesture_capabilities
            except Exception as exc:
                result = GestureResult(False, message=f"Gesture request failed: {exc}")
                capabilities = {}
            self._publish({"type": "gesture_settings", "token": token,
                           "result": result, "capabilities": capabilities})

        threading.Thread(target=work, daemon=True).start()
