"""Track real battery samples for notifications, independently of UI refreshes."""

from utils.battery import battery_state
from utils.i18n import t


class BatteryNotificationState:
    def __init__(self):
        self.active = False
        self._sample = {"left": None, "right": None, "case": None}
        self.inserted = ()

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
        return t("notification.battery_summary", **values,
                 left_label=t("battery.left"), right_label=t("battery.right"), case_label=t("battery.case"))

    def body(self, event, *, last_known=False):
        summary = self.summary()
        if last_known:
            summary = t("notification.last_battery", battery=summary)
        return t("notification.with_battery", event=event, battery=summary)
