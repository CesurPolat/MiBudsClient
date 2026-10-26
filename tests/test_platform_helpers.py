"""Platform fallbacks retain their behavior without playing sounds or loading GI."""

import unittest
from unittest.mock import Mock, call, patch

from utils.sound import play_connection_melody, play_tones
from utils.tray_backend import configure_tray_backend


class SoundTests(unittest.TestCase):
    def test_connection_uses_original_ascending_melody(self):
        with patch("utils.sound.play_tones") as play:
            play_connection_melody()
        play.assert_called_once_with([(880, 80), (1175, 90), (1568, 120)])

    def test_windows_playback_runs_in_background(self):
        sound = Mock()
        with patch("utils.sound.sys.platform", "win32"), patch("utils.sound.winsound", sound), patch(
            "utils.sound.threading.Thread",
        ) as thread:
            play_tones([(880, 80), (1175, 90)])
            sound.Beep.assert_not_called()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            thread.return_value.start.assert_called_once_with()
            thread.call_args.kwargs["target"]()
        self.assertEqual(sound.Beep.call_args_list, [call(880, 80), call(1175, 90)])

    def test_windows_beep_failure_uses_message_beep(self):
        sound = Mock()
        sound.Beep.side_effect = RuntimeError("Unavailable")
        with patch("utils.sound.sys.platform", "win32"), patch("utils.sound.winsound", sound), patch(
            "utils.sound.threading.Thread",
        ) as thread:
            play_tones([(880, 80)])
            thread.call_args.kwargs["target"]()
        sound.MessageBeep.assert_called_once_with(sound.MB_OK)

    def test_linux_prefers_play_then_beep(self):
        for available in ("play", "beep"):
            with self.subTest(available=available), patch("utils.sound.sys.platform", "linux"), patch(
                "utils.sound.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == available else None,
            ), patch("utils.sound.subprocess.run") as run, patch("utils.sound.threading.Thread") as thread:
                play_tones([(880, 80)])
                thread.call_args.kwargs["target"]()
                self.assertEqual(run.call_args.args[0][0], f"/usr/bin/{available}")
                self.assertFalse(run.call_args.kwargs["check"])

    def test_missing_linux_tools_falls_back_to_terminal_bell(self):
        with patch("utils.sound.sys.platform", "linux"), patch("utils.sound.shutil.which", return_value=None), patch(
            "utils.sound.sys.stdout",
        ) as output, patch("utils.sound.time.sleep") as sleep, patch("utils.sound.threading.Thread") as thread:
            play_tones([(880, 80)])
            thread.call_args.kwargs["target"]()
        output.write.assert_called_once_with("\a")
        sleep.assert_called_once_with(0.08)


class TrayBackendTests(unittest.TestCase):
    def test_linux_selects_available_backend_or_leaves_default(self):
        for appindicator, gi, expected in ((True, True, "appindicator"), (False, True, "gtk"), (False, False, None)):
            with self.subTest(expected=expected), patch("utils.tray_backend.sys.platform", "linux"), patch(
                "utils.tray_backend._has_appindicator_namespace", return_value=appindicator,
            ), patch("utils.tray_backend._ensure_gi_module", return_value=gi), patch.dict(
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
