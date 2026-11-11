"""Desktop notification protocol tests without the user's notification server."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from utils.linux_notifications import LinuxNotifications
from ui.system_tray import SystemTray


class Variant:
    def __init__(self, signature, value):
        self.signature, self.value = signature, value
    def unpack(self):
        return self.value


class LinuxNotificationTests(unittest.TestCase):
    def setUp(self):
        self.activate = Mock()
        self.service = LinuxNotifications(self.activate)
        self.service._GLib = SimpleNamespace(Variant=Variant)
        self.service._call = Mock(side_effect=[(['actions', 'body-markup', 'sound'],), (42,)])

    def test_silent_notification_and_actions_use_server_capabilities(self):
        self.service._deliver('A < B & C', 'Earbuds', '', True, 'Open')
        method, params = self.service._call.call_args.args
        self.assertEqual(method, 'Notify')
        self.assertEqual(params.signature, '(susssasa{sv}i)')
        app, replace, icon, title, body, actions, hints, expires = params.value
        self.assertEqual((app, replace, title, body), ('MiBudsClient', 0, 'Earbuds', 'A &lt; B &amp; C'))
        self.assertEqual(actions, ['default', 'Open'])
        self.assertTrue(hints['suppress-sound'].value)
        self.service._signal(None, '', '', '', 'ActionInvoked', Variant('', (42, 'default')))
        self.service._signal(None, '', '', '', 'ActionInvoked', Variant('', (42, 'default')))
        self.activate.assert_called_once()

    def test_server_without_actions_gets_text_and_no_click_claim(self):
        self.service._call.side_effect = [([],), (7,)]
        self.service._deliver('A < B', 'Earbuds', '', True, 'Open')
        values = self.service._call.call_args.args[1].value
        self.assertEqual(values[4:6], ('A < B', []))
        self.assertTrue(values[6]['suppress-sound'].value)
        self.assertFalse(self.service._ids)

    def test_missing_image_falls_back_to_text_without_losing_silence(self):
        self.service._deliver('body', 'title', '/nonexistent/mibuds-image.png', True, 'Open')
        self.assertEqual(self.service._call.call_args.args[1].value[2], '')
        self.assertTrue(self.service._call.call_args.args[1].value[6]['suppress-sound'].value)

    def test_server_image_rejection_retries_once_with_same_sound_and_action_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'image.png'
            image.write_bytes(b'fixture')
            self.service._call.side_effect = [(['actions'],), OSError('image rejected'), (8,)]
            self.service._deliver('body', 'title', str(image), True, 'Open')
        calls = self.service._call.call_args_list
        self.assertTrue(calls[1].args[1].value[2].startswith('file:'))
        self.assertEqual(calls[2].args[1].value[2], '')
        self.assertTrue(calls[2].args[1].value[6]['suppress-sound'].value)
        self.assertEqual(calls[2].args[1].value[5], ['default', 'Open'])

    def test_foreign_closed_and_shutdown_notifications_cannot_activate_window(self):
        self.service._ids.add(42)
        for name, values in (('ActionInvoked', (10, 'default')), ('ActionInvoked', (42, 'other')),
                             ('NotificationClosed', (42, 2)), ('ActionInvoked', (42, 'default'))):
            self.service._signal(None, '', '', '', name, Variant('', values))
        self.activate.assert_not_called()
        self.service._ids.add(8)
        self.service.close()
        self.service._signal(None, '', '', '', 'ActionInvoked', Variant('', (8, 'default')))
        self.activate.assert_not_called()
        self.assertFalse(self.service.notify('late', 'title'))

    def test_enqueue_never_performs_bus_calls_on_caller_thread(self):
        with patch('utils.linux_notifications.threading.Thread') as thread:
            self.assertTrue(self.service.notify('body', 'title'))
        thread.return_value.start.assert_called_once()
        self.service._call.assert_not_called()

    def test_shutdown_before_loop_run_is_handled_by_periodic_source(self):
        self.service._loop = Mock()
        self.service.close()
        self.service._loop.reset_mock()
        self.assertFalse(self.service._drain())
        self.service._loop.quit.assert_called_once()

    def test_failed_delivery_does_not_kill_worker(self):
        self.service._call.side_effect = OSError('server missing')
        self.service._pending.put(('body', 'title', '', True, 'Open'))
        self.assertTrue(self.service._drain())
        self.service._call.side_effect = [([],), (5,)]
        self.service._pending.put(('next', 'title', '', True, 'Open'))
        self.assertTrue(self.service._drain())
        self.assertEqual(self.service._call.call_args.args[0], 'Notify')

    def test_service_owns_glib_context_and_disconnects_on_stop(self):
        service = LinuxNotifications(self.activate)
        glib, gio = Mock(), Mock()
        glib.Variant = Variant
        connection = gio.bus_get_sync.return_value
        connection.signal_subscribe.side_effect = [1, 2, 3]
        loop = glib.MainLoop.new.return_value
        loop.run.side_effect = service.close
        with patch('utils.linux_notifications._ensure_gi_module', return_value=True), patch.dict(
            'sys.modules', {'gi': Mock(), 'gi.repository': SimpleNamespace(Gio=gio, GLib=glib)},
        ):
            service._run()
        context = glib.MainContext.new.return_value
        context.push_thread_default.assert_called_once()
        context.pop_thread_default.assert_called_once()
        self.assertEqual([call.args[0] for call in connection.signal_unsubscribe.call_args_list], [1, 2, 3])
        glib.timeout_source_new.return_value.destroy.assert_called_once()
        # The server can restart and reuse IDs. Never keep old ownership.
        service._ids.add(42)
        connection.signal_subscribe.call_args_list[2].args[-1]()
        self.assertFalse(service._ids)

    def test_system_tray_can_send_without_icon_or_native_loop(self):
        sender = Mock()
        with patch('ui.system_tray.sys.platform', 'linux'), patch('ui.system_tray.LinuxNotifications', return_value=sender):
            tray = SystemTray(Mock(), Mock())
        self.assertFalse(tray.available)
        self.assertIsNone(tray.icon)
        tray.notify('connected', silent=True)
        sender.notify.assert_called_once()
        self.assertTrue(sender.notify.call_args.kwargs['silent'])
        tray.stop()
        sender.close.assert_called_once()
        tray.notify('late')
        self.assertEqual(sender.notify.call_count, 1)
