"""Platform fallbacks retain their behavior without playing sounds or loading GI."""

import unittest
import io
import wave
import struct
import subprocess
from pathlib import Path
from unittest.mock import Mock, call, patch

from utils.sound import play_connection_melody, play_tones, _tone_wave
from utils.tray_backend import configure_tray_backend


class SoundTests(unittest.TestCase):
    def test_connection_uses_original_ascending_melody(self):
        with patch("utils.sound.play_tones") as play:
            play_connection_melody()
        play.assert_called_once_with([(880, 80), (1175, 90), (1568, 120)], delay=1.0)

    def sound_mock(self):
        return Mock(SND_MEMORY=4, SND_NODEFAULT=2, MB_OK=0)

    def test_wave_contains_original_notes_with_stream_warmup(self):
        with wave.open(io.BytesIO(_tone_wave([(880, 80), (1175, 90), (1568, 120)]))) as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 44100))
            self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), 0.44, places=3)
            samples = struct.unpack('<' + 'h' * wav.getnframes(), wav.readframes(wav.getnframes()))
        self.assertTrue(all(value == 0 for value in samples[:6615]))
        offset = 6615
        for frequency, duration in ((880, 80), (1175, 90), (1568, 120)):
            count = round(44100 * duration / 1000)
            note = samples[offset:offset + count]
            crossings = sum(a <= 0 < b for a, b in zip(note, note[1:]))
            self.assertAlmostEqual(crossings * 44100 / count, frequency, delta=20)
            self.assertEqual((note[0], note[-1]), (0, 0))
            offset += count

    def test_windows_playback_runs_in_background(self):
        sound = self.sound_mock()
        with patch("utils.sound.sys.platform", "win32"), patch("utils.sound.winsound", sound), patch(
            "utils.sound.threading.Thread",
        ) as thread:
            play_tones([(880, 80), (1175, 90)])
            sound.Beep.assert_not_called()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            thread.return_value.start.assert_called_once_with()
            thread.call_args.kwargs["target"]()
        sound.PlaySound.assert_called_once()
        self.assertEqual(sound.PlaySound.call_args.args[1], 6)
        self.assertTrue(sound.PlaySound.call_args.args[0].startswith(b'RIFF'))
        sound.Beep.assert_not_called()

    def test_connection_delay_happens_on_the_worker_before_audio(self):
        sound = self.sound_mock()
        order = Mock()
        order.attach_mock(sound.PlaySound, 'play')
        with patch('utils.sound.sys.platform', 'win32'), patch('utils.sound.winsound', sound), patch(
            'utils.sound.time.sleep', order.sleep,
        ), patch('utils.sound.threading.Thread') as thread:
            play_connection_melody()
            order.sleep.assert_not_called()
            thread.call_args.kwargs['target']()
        self.assertEqual(order.mock_calls[0], call.sleep(1.0))
        self.assertEqual(order.mock_calls[1][0], 'play')

    def test_windows_wave_failure_falls_back_to_original_beeps(self):
        sound = self.sound_mock()
        sound.PlaySound.side_effect = RuntimeError('WAV unavailable')
        with patch('utils.sound.sys.platform', 'win32'), patch('utils.sound.winsound', sound), patch(
            'utils.sound.threading.Thread',
        ) as thread:
            play_tones([(880, 80)])
            thread.call_args.kwargs['target']()
        sound.Beep.assert_called_once_with(880, 80)

    def test_windows_beep_failure_uses_message_beep(self):
        sound = self.sound_mock()
        sound.PlaySound.side_effect = RuntimeError('WAV unavailable')
        sound.Beep.side_effect = RuntimeError("Unavailable")
        with patch("utils.sound.sys.platform", "win32"), patch("utils.sound.winsound", sound), patch(
            "utils.sound.threading.Thread",
        ) as thread:
            play_tones([(880, 80)])
            thread.call_args.kwargs["target"]()
        sound.MessageBeep.assert_called_once_with(sound.MB_OK)

    def test_linux_players_receive_complete_wave_and_temporary_file_is_removed(self):
        for available in ("pw-play", "paplay", "aplay", "play"):
            with self.subTest(player=available), patch("utils.sound.sys.platform", "linux"), patch(
                "utils.sound.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == available else None,
            ), patch("utils.sound.subprocess.run") as run, patch("utils.sound.threading.Thread") as thread:
                paths = []
                def playback(command, **kwargs):
                    path = Path(command[-1])
                    paths.append(path)
                    with wave.open(str(path)) as wav:
                        self.assertEqual(wav.getnframes(), round(44100 * .44))
                    self.assertGreater(kwargs["timeout"], .44)
                    return Mock(returncode=0)
                run.side_effect = playback
                play_tones([(880, 80), (1175, 90), (1568, 120)])
                run.assert_not_called()
                thread.call_args.kwargs["target"]()
                self.assertEqual(run.call_args.args[0][0], f"/usr/bin/{available}")
                self.assertEqual(run.call_count, 1)
                self.assertFalse(paths[0].exists())

    def test_linux_falls_back_after_error_exit_timeout_and_missing_binary(self):
        for failure in (Mock(returncode=1, stderr=b"No audio server"),
                        subprocess.TimeoutExpired("pw-play", 3), FileNotFoundError("gone")):
            with self.subTest(failure=failure), patch("utils.sound.sys.platform", "linux"), patch(
                "utils.sound.shutil.which", side_effect=lambda name: f"/usr/bin/{name}",
            ), patch("utils.sound.subprocess.run", side_effect=[failure, Mock(returncode=0)]) as run, patch(
                "utils.sound.threading.Thread",
            ) as thread, patch("builtins.print"):
                play_tones([(880, 80)])
                thread.call_args.kwargs["target"]()
                self.assertEqual([call.args[0][0] for call in run.call_args_list],
                                 ["/usr/bin/pw-play", "/usr/bin/paplay"])

    def test_missing_linux_tools_falls_back_to_terminal_bell(self):
        with patch("utils.sound.sys.platform", "linux"), patch("utils.sound.shutil.which", return_value=None), patch(
            "utils.sound.sys.stdout",
        ) as output, patch("utils.sound.time.sleep") as sleep, patch("utils.sound.threading.Thread") as thread:
            play_tones([(880, 80)])
            thread.call_args.kwargs["target"]()
        self.assertIn(call("\a"), output.write.call_args_list)
        sleep.assert_called_once_with(0.08)


class TrayBackendTests(unittest.TestCase):
    def test_linux_selects_available_backend_or_leaves_default(self):
        for appindicator, gi, expected in ((True, True, "appindicator"), (False, True, "gtk"), (False, False, None)):
            with self.subTest(expected=expected), patch("utils.tray_backend.sys.platform", "linux"), patch(
                "utils.tray_backend._has_appindicator_namespace", return_value=appindicator,
            ), patch("utils.tray_backend._has_gtk_namespace", return_value=gi), patch.dict(
                "utils.tray_backend.os.environ", {}, clear=True,
            ) as environment:
                configure_tray_backend()
                self.assertEqual(environment.get("PYSTRAY_BACKEND"), expected)

    def test_explicit_linux_backend_is_preserved(self):
        with patch("utils.tray_backend.sys.platform", "linux"), patch(
            "utils.tray_backend._has_appindicator_namespace", return_value=True,
        ), patch.dict("utils.tray_backend.os.environ", {"PYSTRAY_BACKEND": "xorg"}, clear=True) as environment:
            configure_tray_backend()
            self.assertEqual(environment["PYSTRAY_BACKEND"], "xorg")

    def test_windows_does_not_probe_linux_backend(self):
        with patch("utils.tray_backend.sys.platform", "win32"), patch(
            "utils.tray_backend._has_appindicator_namespace",
        ) as probe:
            configure_tray_backend()
        probe.assert_not_called()
