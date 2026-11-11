"""Sway, Hyprland and Plasma responses without accessing a real compositor."""
import json
import os
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import patch

from utils import wayland
from utils.wayland_setup import ensure_wayland_support


def response(data):
    return SimpleNamespace(stdout=json.dumps(data), returncode=0)


def sway_window(**changes):
    data = dict(type='con', focused=True, app_id='Game', pid=0, fullscreen_mode=1,
                nodes=[], floating_nodes=[])
    data.update(changes)
    return data


def sway_tree(window):
    return dict(type='root', nodes=[dict(type='output', nodes=[dict(type='workspace', nodes=[window])])])


class SwayDetectionTests(unittest.TestCase):
    def test_native_floating_and_xwayland_windows(self):
        for window, expected in (
            (sway_window(), (True, 'game')),
            (sway_window(fullscreen_mode=0), (False, 'game')),
            (sway_window(fullscreen_mode=2), (True, 'game')),
            (sway_window(app_id=None, window_properties={'class': 'WineGame.exe'}), (True, 'winegame.exe')),
        ):
            tree = {'type': 'root', 'floating_nodes': [window]}
            with self.subTest(window=window), patch('utils.wayland.subprocess.run', return_value=response(tree)) as run:
                self.assertEqual(wayland.detect_sway_fullscreen(), expected)
                self.assertEqual(run.call_args.args[0], ['swaymsg', '-r', '-t', 'get_tree'])

    def test_fullscreen_container_applies_to_focused_child(self):
        tree = sway_tree(dict(type='con', fullscreen_mode=1, nodes=[sway_window(fullscreen_mode=0)]))
        with patch('utils.wayland.subprocess.run', return_value=response(tree)):
            self.assertEqual(wayland.detect_sway_fullscreen(), (True, 'game'))

    def test_background_fullscreen_does_not_activate_foreground_window(self):
        tree = dict(type='root', nodes=[sway_window(focused=False), sway_window(app_id='Terminal', fullscreen_mode=0)])
        with patch('utils.wayland.subprocess.run', return_value=response(tree)):
            self.assertEqual(wayland.detect_sway_fullscreen(), (False, 'terminal'))

    def test_no_focus_is_false_and_invalid_reply_is_unknown(self):
        for tree, expected in (
            ({'type': 'root', 'nodes': []}, (False, '')),
            (sway_tree(sway_window(focused=False)), (False, '')),
            (sway_tree(sway_window(fullscreen_mode='yes')), (None, '')),
            ({'type': 'root', 'nodes': 'bad'}, (None, '')),
            ([], (None, '')), ({}, (None, '')),
        ):
            with self.subTest(tree=tree), patch('utils.wayland.subprocess.run', return_value=response(tree)):
                self.assertEqual(wayland.detect_sway_fullscreen(), expected)


class HyprlandDetectionTests(unittest.TestCase):
    def test_true_fullscreen_is_distinguished_from_maximized(self):
        for mode, expected in ((0, False), (1, False), (2, True), (3, True), (True, True), (False, False)):
            with self.subTest(mode=mode), patch('utils.wayland.subprocess.run', return_value=response({'class': 'Game', 'fullscreen': mode})) as run:
                self.assertEqual(wayland.detect_hyprland_fullscreen(), (expected, 'game'))
                self.assertEqual(run.call_args.args[0], ['hyprctl', '-j', 'activewindow'])

    def test_internal_compositor_state_takes_precedence_over_client_request(self):
        with patch('utils.wayland.subprocess.run', return_value=response({'class': 'Game', 'fullscreen': 0, 'fullscreenClient': 2})):
            self.assertEqual(wayland.detect_hyprland_fullscreen(), (False, 'game'))

    def test_empty_and_invalid_replies(self):
        for data, expected in (({}, (False, '')), ({'fullscreen': 'yes'}, (None, '')),
                               ({'fullscreen': 9}, (None, '')), ([], (None, ''))):
            with self.subTest(data=data), patch('utils.wayland.subprocess.run', return_value=response(data)):
                self.assertEqual(wayland.detect_hyprland_fullscreen(), expected)


class KdeDetectionTests(unittest.TestCase):
    def test_bundled_readonly_script_uses_kdotool(self):
        with patch('utils.wayland.subprocess.run', return_value=response(
            dict(available=True, fullscreen=True, app_id='Game', pid=123),
        )) as run, patch('utils.wayland.os.readlink', return_value='/usr/games/MyGame'):
            self.assertEqual(wayland.detect_kde_fullscreen(), (True, 'mygame'))
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ['kdotool', 'kwinscript', '--file'])
        self.assertTrue(command[-1].endswith('assets/kwin/fullscreen.js'))
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertEqual(run.call_args.kwargs['timeout'], 1.5)

    def test_no_active_window_and_invalid_script_response(self):
        for state, expected in (
            (dict(available=True, fullscreen=False, app_id='', pid=0), (False, '')),
            (dict(available=False, fullscreen=False), (None, '')),
            (dict(available=True, fullscreen=1), (None, '')),
        ):
            with self.subTest(state=state), patch('utils.wayland.subprocess.run', return_value=response(state)):
                self.assertEqual(wayland.detect_kde_fullscreen(), expected)


class CompositorRoutingTests(unittest.TestCase):
    def test_selected_desktop_uses_only_its_own_backend(self):
        for desktop, name in (('KDE', 'kde'), ('sway', 'sway'), ('Hyprland', 'hyprland'), ('zorin:GNOME', 'gnome')):
            with self.subTest(desktop=desktop), patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': desktop}, clear=True), patch(
                f'utils.wayland.detect_{name}_fullscreen', return_value=(True, 'game'),
            ) as detect:
                self.assertEqual(wayland.detect_wayland_fullscreen(), (True, 'game'))
                detect.assert_called_once()

    def test_compositor_socket_identifies_sessions_without_desktop_variable(self):
        for variable, name in (('SWAYSOCK', 'sway'), ('HYPRLAND_INSTANCE_SIGNATURE', 'hyprland')):
            with patch.dict(os.environ, {variable: 'socket'}, clear=True):
                self.assertEqual(wayland.compositor(), name)

    def test_unknown_desktop_does_not_probe_other_compositors(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'Weston'}, clear=True), patch(
            'utils.wayland.subprocess.run', side_effect=AssertionError('Unexpected query'),
        ):
            self.assertEqual(wayland.detect_wayland_fullscreen(), (None, ''))

    def test_new_backends_need_tools_but_do_not_install_gnome_extensions(self):
        for desktop, tool in (('KDE', 'kdotool'), ('sway', 'swaymsg'), ('Hyprland', 'hyprctl')):
            for present in (False, True):
                with self.subTest(desktop=desktop, present=present), patch.dict(os.environ, {
                    'XDG_CURRENT_DESKTOP': desktop, 'XDG_SESSION_TYPE': 'wayland',
                }, clear=True), patch('utils.wayland_setup.shutil.which', return_value='/bin/' + tool if present else None) as which, patch(
                    'utils.wayland_setup.ensure_gnome_bridge', side_effect=AssertionError('Unexpected GNOME setup'),
                ):
                    self.assertEqual(ensure_wayland_support(), 'ready' if present else 'unavailable')
                    which.assert_called_once_with(tool)

    def test_process_failures_and_malformed_json_remain_unknown(self):
        for detect in (wayland.detect_sway_fullscreen, wayland.detect_hyprland_fullscreen, wayland.detect_kde_fullscreen):
            for failure in (FileNotFoundError(), subprocess.TimeoutExpired('compositor', 1.5),
                            subprocess.CalledProcessError(1, 'compositor'), response('not a state')):
                with self.subTest(backend=detect.__name__, failure=failure), patch('utils.wayland.subprocess.run') as run:
                    if isinstance(failure, Exception):
                        run.side_effect = failure
                    else:
                        run.return_value = failure
                    self.assertEqual(detect(), (None, ''))
