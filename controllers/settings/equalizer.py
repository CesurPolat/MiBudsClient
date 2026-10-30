from utils.error_reports import publish_exception
"""Execute EQ work outside Flet and reject completions from old connections."""
import threading

from utils.i18n import message as m, error_message
from controllers.bluetooth.equalizer import EqResult


class EqSettingsController:
    def __init__(self, controller, panel, publish):
        self._controller = controller
        self._panel = panel
        self._publish = publish

    def action(self, operation, **kwargs):
        session = self._controller.eq_session
        token = self._panel.begin(operation)
        if token is None:
            return

        def work():
            try:
                if operation == "read":
                    result = self._controller.request_eq_settings(session=session)
                else:
                    result = self._controller.apply_eq(operation, session=session, **kwargs)
                profiles = self._controller.eq_profiles
                if self._controller.eq_session != session:
                    return
            except Exception as exc:
                publish_exception(self._publish, exc, "equalizer")
                result = EqResult(False, message=m("eq.failed", details=error_message(exc)))
                profiles = ()
            self._publish({"type": "eq_settings", "token": token, "result": result,
                           "profiles": profiles, "operation": operation})

        threading.Thread(target=work, daemon=True).start()
