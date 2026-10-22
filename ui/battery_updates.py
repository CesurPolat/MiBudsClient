"""Publish battery refreshes and play charging transition notifications."""

import shutil
import subprocess
import sys
import threading
import time
from typing import Callable

try:
    import winsound
except ImportError:
    winsound = None

from .constants import BATTERY_UNKNOWN, BATTERY_CHARGING_OFFSET


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

        def _play_tones():
            if winsound and sys.platform.startswith("win"):
                try:
                    for frequency, duration in tones:
                        winsound.Beep(frequency, duration)
                    return
                except RuntimeError:
                    winsound.MessageBeep(winsound.MB_OK)
                    return

            if sys.platform.startswith("linux"):
                play_bin = shutil.which("play")
                beep_bin = shutil.which("beep")

                if play_bin:
                    for frequency, duration in tones:
                        subprocess.run(
                            [
                                play_bin,
                                "-nq",
                                "synth",
                                f"{duration / 1000:.3f}",
                                "sine",
                                str(frequency),
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    return

                if beep_bin:
                    for frequency, duration in tones:
                        subprocess.run(
                            [beep_bin, "-f", str(frequency), "-l", str(duration)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                    return

            # Last-resort fallback: terminal bell pattern.
            for _, duration in tones:
                try:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                except Exception:
                    pass
                time.sleep(duration / 1000)

        threading.Thread(target=_play_tones, daemon=True).start()

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
