"""Publish battery refreshes and play the app's own case-transition melodies."""

import time
from typing import Callable

from utils.battery import battery_state
from utils.sound import play_tones
from ui.constants import BATTERY_UNKNOWN


class BatteryUpdates:
    """Adapt the Bluetooth callback into UI messages without touching controls."""

    def __init__(self, publish: Callable[[dict], None]):
        self._publish = publish
        self._previous_charging_state = {"left": None, "right": None}

    @staticmethod
    def get_charging_state(raw_value):
        state = battery_state(raw_value)
        return state[1] if state is not None else None

    @staticmethod
    def play_charge_transition_sound(started):
        start_pattern = [(880, 80), (1175, 90), (1568, 120)]
        stop_pattern = [(1568, 80), (1175, 90), (880, 120)]
        play_tones(start_pattern if started else stop_pattern)

    def update(self, left, right, case):
        for side, raw_value in (("left", left), ("right", right)):
            previous = self._previous_charging_state[side]
            current = self.get_charging_state(raw_value)
            if previous is not None and current is not None and previous != current:
                self.play_charge_transition_sound(started=current)
            self._previous_charging_state[side] = current

        # UX hint: briefly clear battery fields before showing the latest values,
        # even when values are unchanged.
        self._publish({
            "type": "battery",
            "left": BATTERY_UNKNOWN,
            "right": BATTERY_UNKNOWN,
            "case": BATTERY_UNKNOWN,
            "transient": True
        })
        time.sleep(0.2)
        self._publish({
            "type": "battery",
            "left": left,
            "right": right,
            "case": case,
            "transient": False
        })
