"""Track battery samples and handle connection and charging case notifications."""

import threading

from controllers.battery.stream import battery_state
from utils.app.i18n import t
from utils.app.pubsub_topics import PubSubTopic
from utils.notifications.sound import play_connection_melody, play_disconnection_melody


class BatteryNotificationState:
    def __init__(self):
        self.active = False
        self._sample = {"left": None, "right": None, "case": None}
        self.inserted = ()
        self.single_body = False

    def reset(self, *, active=False):
        self.active = active
        self._sample = dict.fromkeys(self._sample)
        self.inserted = ()

    def update(self, left, right, case) -> tuple[str, ...]:
        """Return removed sides and expose inserted sides from this same sample."""
        self.inserted = ()
        if not self.active:
            return ()
        sample = {name: battery_state(raw) for name, raw in
                  zip(("left", "right", "case"), (left, right, case))}
        removed = tuple(side for side in ("left", "right")
                        if self._sample[side] is not None and sample[side] is not None
                        and self._sample[side][1] and not sample[side][1])
        self.inserted = tuple(side for side in ("left", "right")
                              if self._sample[side] is not None and sample[side] is not None
                              and not self._sample[side][1] and sample[side][1])
        # Unknown/invalid samples break the baseline: never infer a transition
        # across an unknown interval or use a stale percentage as current data.
        self._sample = sample
        return removed

    @property
    def has_earbud_data(self):
        return any(self._sample[side] is not None for side in ("left", "right"))

    def summary(self):
        values = {}
        for name, state in self._sample.items():
            if state is None:
                values[name] = "—"
            else:
                level = t("notification.battery_percent", percent=state[0])
                values[name] = t("notification.battery_charging", level=level) if state[1] else level
        if self.single_body:
            return f'{t("battery.device")}: {values["left"]}'
        return t("notification.battery_summary", **values,
                 left_label=t("battery.left"), right_label=t("battery.right"), case_label=t("battery.case"))

    def body(self, event, *, last_known=False):
        summary = self.summary()
        if last_known:
            summary = t("notification.last_battery", battery=summary)
        return t("notification.with_battery", event=event, battery=summary)


class BatteryNotifications:
    def __init__(self, *, publish, notify, on_disconnect):
        self._publish = publish
        self._notify = notify
        self._on_disconnect = on_disconnect
        self._state = BatteryNotificationState()
        self._lock = threading.RLock()
        self._last_connection_event = None
        self._connection_melody_played = False
        self._timer = None
        self._token = 0
        self._stopped = False

    def routes(self):
        return {
            PubSubTopic.CONNECTION_EVENT.value: self.on_connection_event,
            PubSubTopic.CONNECTION_NOTIFICATION_TIMEOUT.value: self.on_connection_timeout,
        }

    def set_single_body(self, single_body):
        with self._lock:
            self._state.single_body = single_body

    def on_connection_state(self, state):
        if state in {"connecting", "failed"}:
            with self._lock:
                # Keep the last sample for the disconnect notice, ignoring late samples.
                self._state.active = False

    def on_connection_event(self, message):
        event = message.get("event")
        if event not in ("connected", "disconnected"):
            return
        with self._lock:
            if self._stopped or event == self._last_connection_event:
                return
            previous_event = self._last_connection_event
            self._last_connection_event = event
            self._cancel_timer()
            if event == "connected":
                if not self._connection_melody_played:
                    self._connection_melody_played = True
                    play_connection_melody()
                self._state.reset(active=True)
                token = self._token
                # The timer only publishes. Notifications run on the UI event path.
                self._timer = threading.Timer(3.0, lambda: self._publish(
                    {"type": PubSubTopic.CONNECTION_NOTIFICATION_TIMEOUT.value, "token": token}
                ))
                self._timer.daemon = True
                self._timer.start()
            else:
                if previous_event == "connected":
                    play_disconnection_melody()
                self._on_disconnect()
                self._show(t("tray.disconnected"), last_known=True)
                self._state.reset()

    def on_battery(self, left, right, case, *, transient):
        if transient:
            return
        with self._lock:
            removed = self._state.update(left, right, case)
            inserted = self._state.inserted
            if self._timer is not None and self._state.active and self._state.has_earbud_data:
                self._show_connected()
            elif removed and inserted:
                self._show(t("notification.case_changes", removed=self._case_event("removed", removed),
                             inserted=self._case_event("inserted", inserted)))
            elif removed:
                self._show(self._case_event("removed", removed))
            elif inserted:
                self._show(self._case_event("inserted", inserted))

    def on_connection_timeout(self, message):
        with self._lock:
            if message.get("token") == self._token and self._timer is not None and self._state.active:
                self._show_connected()

    def stop(self):
        with self._lock:
            self._stopped = True
            self._cancel_timer()
            self._state.reset()

    def _cancel_timer(self):
        self._token += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _show_connected(self):
        self._cancel_timer()
        self._show(t("tray.connected"))

    def _show(self, event, *, last_known=False):
        self._notify(self._state.body(event, last_known=last_known), device=True, silent=True)

    @staticmethod
    def _case_event(kind, sides):
        side = "both" if len(sides) == 2 else sides[0]
        return t("notification." + kind + "_" + side)
