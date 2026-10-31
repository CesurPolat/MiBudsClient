"""Background noise transactions, delivered through the existing UI pubsub."""
import threading
from utils.i18n import message as m, error_message


class NoiseSettingsController:
    def __init__(self, controller, panel, publish):
        self.controller, self.panel, self.publish = controller, panel, publish
        controller.noise_callback = lambda session, state: publish(
            {"type": "noise_notification", "session": session, "state": state})

    def action(self, operation, **kwargs):
        session = self.controller.eq_session
        token = self.panel.begin(operation, session)
        if token is None:
            return

        def work():
            state, error = None, None
            try:
                if operation == "read":
                    state = self.controller.request_noise_settings(session=session)
                elif operation == "write":
                    state = self.controller.set_noise_settings(session=session, **kwargs)
                else:
                    raise ValueError("Unknown noise operation")
            except (OSError, ValueError) as exc:
                error = m("noise.failed", details=error_message(exc))
            if session == self.controller.eq_session:
                self.publish({"type": "noise_settings", "token": token,
                              "state": state, "error": error})

        threading.Thread(target=work, daemon=True).start()
