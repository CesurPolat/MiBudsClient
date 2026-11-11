"""Compositor replies are synthetic; tests do not access the user's desktop."""
import json
import os
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import Mock, patch

from utils.game_monitor import FullscreenGameMonitor
from utils.wayland import detect_gnome_fullscreen


def reply(**changes):
    state = dict(version=1, available=True, fullscreen=True,
                 app_id='org.example.Game', pid=123)
    state.update(changes)
    return SimpleNamespace(returncode=0, stdout=repr((json.dumps(state),)))


class GnomeBridgeTests(unittest.TestCase):
    def test_fullscreen_and_executable_identity_from_bridge(self):
        with patch('utils.wayland.subprocess.run', return_value=reply()) as run, patch(
            'utils.wayland.os.readlink', return_value='/usr/games/SuperTuxKart',
        ):
            self.assertEqual(detect_gnome_fullscreen(), (True, 'supertuxkart'))
        command = run.call_args.args[0]
        self.assertEqual(command[0], 'gdbus')
        self.assertIn('org.mibuds.Fullscreen.GetState', command)
        self.assertGreater(run.call_args.kwargs['timeout'], 0)

    def test_missing_proc_entry_falls_back_to_application_identity(self):
        with patch('utils.wayland.subprocess.run', return_value=reply()), patch(
            'utils.wayland.os.readlink', side_effect=FileNotFoundError(),
        ):
            self.assertEqual(detect_gnome_fullscreen(), (True, 'org.example.game'))

    def test_normal_window_is_not_fullscreen(self):
        with patch('utils.wayland.subprocess.run', return_value=reply(fullscreen=False, pid=0)):
            self.assertEqual(detect_gnome_fullscreen(), (False, 'org.example.game'))

    def test_overview_lock_and_no_focus_have_no_active_game(self):
        with patch('utils.wayland.subprocess.run', return_value=reply(fullscreen=False, app_id='', pid=0)):
            self.assertEqual(detect_gnome_fullscreen(), (False, ''))

    def test_unavailable_bridge_missing_tool_timeout_and_bad_reply_are_unknown(self):
        invalid = [
            reply(available=False), reply(version=2), reply(fullscreen=1), reply(app_id=None),
            SimpleNamespace(returncode=1, stdout=''),
            SimpleNamespace(returncode=0, stdout='not a tuple'),
            SimpleNamespace(returncode=0, stdout=repr(('not JSON',))),
            SimpleNamespace(returncode=0, stdout=repr(('[]',))),
            SimpleNamespace(returncode=0, stdout=repr(('{}', 'extra'))),
            FileNotFoundError(), subprocess.TimeoutExpired('gdbus', 1.5),
        ]
        for result in invalid:
            with self.subTest(result=result), patch('utils.wayland.subprocess.run') as run:
                if isinstance(result, Exception):
                    run.side_effect = result
                else:
                    run.return_value = result
                self.assertEqual(detect_gnome_fullscreen(), (None, ''))

    def test_reply_is_not_executed_as_python(self):
        result = SimpleNamespace(returncode=0, stdout="(__import__('os').getcwd(),)")
        with patch('utils.wayland.subprocess.run', return_value=result), patch('utils.wayland.os.getcwd') as execute:
            self.assertEqual(detect_gnome_fullscreen(), (None, ''))
        execute.assert_not_called()

    def test_bridge_can_be_enabled_after_an_unavailable_poll(self):
        with patch('utils.wayland.subprocess.run', side_effect=[
            SimpleNamespace(returncode=1), reply(pid=0),
        ]):
            self.assertEqual(detect_gnome_fullscreen(), (None, ''))
            self.assertEqual(detect_gnome_fullscreen(), (True, 'org.example.game'))


class MonitorRoutingTests(unittest.TestCase):
    def monitor(self):
        return FullscreenGameMonitor(Mock(), on_log=Mock())

    def test_zorin_and_gnome_wayland_use_bridge_without_x11_queries(self):
        for desktop in ('zorin:GNOME', 'ubuntu:GNOME', 'GNOME'):
            with self.subTest(desktop=desktop), patch.dict(os.environ, {
                'XDG_CURRENT_DESKTOP': desktop, 'XDG_SESSION_TYPE': 'wayland',
                'WAYLAND_DISPLAY': '',
            }, clear=True), patch('utils.game_monitor.detect_wayland_fullscreen', return_value=(True, 'game')) as bridge, patch(
                'utils.game_monitor.subprocess.run', side_effect=AssertionError('Unexpected X11 query'),
            ):
                self.assertEqual(self.monitor()._detect_linux_fullscreen(), (True, 'game'))
                bridge.assert_called_once()

    def test_other_wayland_compositors_do_not_guess_from_xwayland(self):
        with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-0', 'XDG_CURRENT_DESKTOP': 'Weston'}, clear=True), patch(
            'utils.game_monitor.subprocess.run', side_effect=AssertionError('Unexpected X11 query'),
        ):
            self.assertEqual(self.monitor()._detect_linux_fullscreen(), (None, ''))

    def test_x11_retains_existing_detector(self):
        with patch.dict(os.environ, {'XDG_SESSION_TYPE': 'x11'}, clear=True), patch(
            'utils.game_monitor.subprocess.run', return_value=SimpleNamespace(stdout='_NET_ACTIVE_WINDOW(WINDOW): window id # 0x0', returncode=0),
        ) as run:
            self.assertEqual(self.monitor()._detect_linux_fullscreen(), (False, ''))
        self.assertEqual(run.call_args.args[0], ['xprop', '-root', '_NET_ACTIVE_WINDOW'])

    def test_unknown_poll_resets_stabilization_and_does_not_emit_false(self):
        monitor = self.monitor()
        states = iter([(True, 'game'), (None, ''), (True, 'game'), (True, 'game')])
        seen = []
        def detect():
            seen.append(monitor._on_fullscreen_change.call_count)
            return next(states)
        def sleep(_):
            if len(seen) == 4:
                monitor._running = False
        monitor._running = True
        with patch.object(monitor, '_detect_fullscreen_state', side_effect=detect), patch('utils.game_monitor.time.sleep', side_effect=sleep), patch('utils.game_monitor.ensure_wayland_support', return_value='ready'):
            monitor._run_loop()
        self.assertEqual(seen, [0, 0, 0, 0])
        monitor._on_fullscreen_change.assert_called_once_with(True, 'game')
