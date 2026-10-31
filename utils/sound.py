"""Asynchronous tone playback with Windows and Linux fallbacks."""

import shutil
import io
import math
import struct
import subprocess
import sys
import threading
import time
import wave
from typing import Sequence

try:
    import winsound
except ImportError:
    winsound = None

_playback_lock = threading.Lock()


def _tone_wave(tones: Sequence[tuple[int, int]]) -> bytes:
    """Render the entire melody into one mono, 16-bit PCM WAV stream."""
    rate = 44100
    # Warm up the output stream before the first short note.
    samples = bytearray(int(rate * 0.15) * 2)
    for frequency, duration in tones:
        count = round(rate * duration / 1000)
        ramp = max(1, min(round(rate * 0.005), count // 2))
        for index in range(count):
            envelope = min(1.0, index / ramp, (count - 1 - index) / ramp)
            value = round(11000 * envelope * math.sin(2 * math.pi * frequency * index / rate))
            samples.extend(struct.pack('<h', value))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples)
    return buffer.getvalue()


def play_connection_melody() -> None:
    """Use the existing ascending melody for the app's first successful connection."""
    # RFCOMM can connect before the OS finishes switching its audio output.
    play_tones([(880, 80), (1175, 90), (1568, 120)], delay=1.0)


def play_disconnection_melody() -> None:
    """Descending counterpart to the connection melody, on the active output."""
    play_tones([(1568, 80), (1175, 90), (880, 120)], delay=0.5)


def play_exit_melody() -> None:
    """Let the short goodbye finish during normal interpreter shutdown."""
    play_tones([(1175, 80), (880, 90), (659, 120)], daemon=False)


def play_tones(tones: Sequence[tuple[int, int]], *, delay: float = 0.0, daemon: bool = True) -> None:
    """Play (frequency Hz, duration ms) pairs without blocking the caller."""
    tones = tuple(tones)

    def _play_tones():
        if delay > 0:
            time.sleep(delay)
        if winsound and sys.platform.startswith("win"):
            # SND_MEMORY is synchronous; run it on this worker, never the UI thread.
            # Serialize melodies so a second PlaySound cannot interrupt the first.
            with _playback_lock:
                try:
                    winsound.PlaySound(_tone_wave(tones), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
                    return
                except RuntimeError:
                    try:
                        for frequency, duration in tones:
                            winsound.Beep(frequency, duration)
                        return
                    except RuntimeError:
                        try:
                            winsound.MessageBeep(winsound.MB_OK)
                            return
                        except RuntimeError as error:
                            print(f"Audio playback unavailable: {error}")
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

    threading.Thread(target=_play_tones, daemon=daemon).start()
