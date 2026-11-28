from utils.diagnostics.error_reports import publish_exception
"""Run gesture requests off the UI thread and publish versioned completions."""

from utils.app.i18n import message as m, error_message
from utils.app.pubsub_topics import PubSubTopic

import threading

from .protocol import GestureResult


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
        token = self._panel.begin(m("gesture.saving") if assignment else m("gesture.reading"))
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
                publish_exception(self._publish, exc, "gestures")
                result = GestureResult(False, message=m("gesture.failed", details=error_message(exc)))
                capabilities = {}
            self._publish(PubSubTopic.GESTURE_SETTINGS, token=token,
                           result=result, capabilities=capabilities)

        threading.Thread(target=work, daemon=True).start()
