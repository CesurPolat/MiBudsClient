"""Asynchronous tone playback with Windows and Linux fallbacks."""

import shutil
import subprocess
import sys
import threading
import time
from typing import Sequence

try:
    import winsound
except ImportError:
    winsound = None


def play_connection_melody() -> None:
    """Use the existing ascending melody for the app's first successful connection."""
    play_tones([(880, 80), (1175, 90), (1568, 120)])


def play_tones(tones: Sequence[tuple[int, int]]) -> None:
    """Play (frequency Hz, duration ms) pairs without blocking the caller."""
    tones = tuple(tones)

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
