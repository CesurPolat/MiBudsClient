"""Publish battery refreshes and play charging transition notifications."""

import time
from typing import Callable

from utils.sound import play_tones
from ui.constants import BATTERY_UNKNOWN, BATTERY_CHARGING_OFFSET


class BatteryUpdates:
    """Adapt the Bluetooth callback into UI messages without touching controls."""

    def __init__(self, publish: Callable[[dict], None]):
        self._publish = publish
        self._previous_charging_state = {
            "left": None,
            "right": None,
        }

    @staticmethod
    def get_charging_state(raw_value):
        """Return charging state for a raw battery value, or None if unknown."""
        if raw_value == BATTERY_UNKNOWN:
            return None
        return raw_value >= BATTERY_CHARGING_OFFSET

    @staticmethod
    def play_charge_transition_sound(started):
        """Play distinct tone patterns for charge transitions on Windows/Linux."""
        start_pattern = [(880, 80), (1175, 90), (1568, 120)]
        stop_pattern = [(1568, 80), (1175, 90), (880, 120)]
        tones = start_pattern if started else stop_pattern

        play_tones(tones)

    def update(self, left, right, case):
        current_charging_state = {
            "left": self.get_charging_state(left),
            "right": self.get_charging_state(right),
        }

        for side in ("left", "right"):
            previous_state = self._previous_charging_state[side]
            current_state = current_charging_state[side]

            if previous_state is None or current_state is None:
                self._previous_charging_state[side] = current_state
                continue

            if not previous_state and current_state:
                self.play_charge_transition_sound(started=True)
            elif previous_state and not current_state:
                self.play_charge_transition_sound(started=False)

            self._previous_charging_state[side] = current_state

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
