import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from utils.error_reports import (DeliveryError, ErrorReportClient, ErrorReportManager,
                                 ReportQueue, encode_report, make_report, redact,
                                 guard_ui_callbacks, queue_directory)
from ui.components.error_report import ErrorReportDialog
from utils.debug_console import DebugConsoleManager


class ErrorReportTests(unittest.TestCase):
    def test_pubsub_dispatch_serializes_control_updates(self):
        from ui.app_message_handler import AppMessageHandler
        handler = AppMessageHandler.__new__(AppMessageHandler)
        handler._closing = False
        handler._dispatch_lock = threading.RLock()
        first_entered, release_first, second_entered = (threading.Event() for _ in range(3))
        def first(message):
            first_entered.set()
            release_first.wait(2)
        handler._routes = {'first': first, 'second': lambda message: second_entered.set()}
        threads = [threading.Thread(target=handler.handle, args=({'type': kind},))
                   for kind in ('first', 'second')]
        threads[0].start()
        self.assertTrue(first_entered.wait(2))
        threads[1].start()
        try:
            self.assertFalse(second_entered.wait(0.05))
        finally:
            release_first.set()
            for thread in threads:
                thread.join(2)
        self.assertTrue(second_entered.is_set())

    def report_page(self, visible=True):
        page = SimpleNamespace(window=SimpleNamespace(visible=visible), overlay=[], update=Mock())
        def show_dialog(control):
            control.open = True
            control.update = Mock()
        page.show_dialog = Mock(side_effect=show_dialog)
        return page

    def test_ui_callback_failures_are_captured(self):
        import flet as ft
        capture = Mock()
        def fail(e):
            raise ValueError('callback')
        button = ft.TextButton('test', on_click=fail)
        guard_ui_callbacks([button], capture)
        button.on_click(None)
        self.assertIsInstance(capture.call_args.args[0], ValueError)

    def test_platform_queue_paths(self):
        with patch('utils.error_reports.sys.platform', 'win32'), patch.dict('os.environ', {'LOCALAPPDATA': 'local-data'}):
            self.assertEqual(queue_directory(), Path('local-data/MiBudsClient/error_reports'))
        with patch('utils.error_reports.sys.platform', 'linux'), patch.dict('os.environ', {'XDG_DATA_HOME': 'linux-data'}):
            self.assertEqual(queue_directory(), Path('linux-data/MiBudsClient/error_reports'))

    def test_redaction_and_stack_excludes_source(self):
        try:
            raise ValueError('token=abc password=xyz AA:BB:CC:DD:EE:FF user@example.com https://host/private')
        except ValueError as error:
            report = make_report(error)
        self.assertNotIn('abc', report['message'])
        self.assertNotIn('xyz', report['message'])
        self.assertNotIn('AA:BB', report['message'])
        self.assertNotIn('raise ValueError', report['stack'])
        self.assertNotIn(str(Path.home()), redact(str(Path.home()) + '/private'))
        self.assertIn('test_error_reports.py:', report['stack'])

    def test_unicode_budget(self):
        report = make_report(ValueError('\U0001f600' * 10000))
        report['details']['description'] = '\U0001f600' * 4000
        self.assertLessEqual(len(encode_report(report)), 65536)
        with self.assertRaises(ValueError):
            encode_report({'message': '\U0001f600' * 20000})

    def test_deduplication_and_reporter_failure(self):
        publish = Mock()
        manager = ErrorReportManager(publish=publish, app_version='v1.0', get_device=lambda: '')
        manager.capture(ValueError('same'))
        manager.capture(ValueError('same'))
        self.assertEqual(publish.call_count, 1)
        publish.side_effect = RuntimeError('reporter failed')
        manager.capture(ValueError('different'))

    def test_dialog_consent_hidden_preview_and_double_send(self):
        page = self.report_page(visible=False)
        queue = Mock()
        dialog = ErrorReportDialog(page, queue)
        dialog.receive(make_report(ValueError('test')))
        queue.enqueue.assert_not_called()
        self.assertIsNone(dialog.active)
        page.window.visible = True
        dialog.show_pending()
        control = dialog.active
        field = control.content.content.controls[1]
        field.value = 'I clicked connect'
        field.on_change(None)
        preview = control.content.content.controls[3].controls[0]
        self.assertEqual(json.loads(preview.value)['details']['description'], field.value)
        button = control.actions[1]
        button.on_click(None)
        button.on_click(None)
        queue.enqueue.assert_called_once()
        self.assertFalse(control.open)
        self.assertIs(dialog.active, control)  # Retained until native dismiss acknowledgement.
        self.assertEqual(page.overlay, [])
        control.on_dismiss(None)
        dialog.receive(make_report(ValueError('cancel')))
        dialog.active.actions[0].on_click(None)
        queue.enqueue.assert_called_once()

    def test_save_failure_keeps_description_and_enables_retry(self):
        page, queue = self.report_page(), Mock()
        queue.enqueue.side_effect = [False, True]
        manager = ErrorReportDialog(page, queue)
        manager.receive(make_report(ValueError('test')))
        control = manager.active
        field = control.content.content.controls[1]
        field.value = 'opening the app'
        send = control.actions[1]
        send.on_click(None)
        self.assertFalse(send.disabled)
        self.assertTrue(control.open)
        self.assertEqual(field.value, 'opening the app')
        self.assertTrue(control.content.content.controls[-1].visible)
        send.on_click(None)
        self.assertEqual(queue.enqueue.call_count, 2)
        self.assertFalse(control.open)

    def test_pending_dialog_waits_for_native_dismissal(self):
        page = self.report_page()
        manager = ErrorReportDialog(page, Mock())
        manager.receive(make_report(ValueError('first')))
        first = manager.active
        manager.receive(make_report(ValueError('second')))
        first.actions[0].on_click(None)
        page.show_dialog.assert_called_once_with(first)
        first.on_dismiss(None)
        self.assertIsNot(manager.active, first)
        self.assertEqual(page.show_dialog.call_count, 2)

    def test_status_uses_managed_dialogs_without_removing_overlay_controls(self):
        page = self.report_page()
        existing = object()
        page.overlay.append(existing)
        manager = ErrorReportDialog(page, Mock())
        manager.status('queued')
        first = manager.snack
        manager.status('sent')
        self.assertFalse(first.open)
        first.update.assert_called_once()
        self.assertEqual(page.overlay, [existing])

    def test_hooks_preserve_original(self):
        callback = Mock()
        manager = DebugConsoleManager(on_exception=callback)
        manager._orig_excepthook = Mock()
        error = ValueError('test')
        manager._handle_exception(ValueError, error, None)
        callback.assert_called_once_with(error, tb=None)
        manager._orig_excepthook.assert_called_once()
        manager._orig_threading_hook = Mock()
        manager._handle_thread_exception(SimpleNamespace(exc_type=ValueError, exc_value=error, exc_traceback=None))
        self.assertEqual(callback.call_count, 2)

    def test_http_contract_and_retry_after(self):
        response = Mock(status=201)
        response.read.return_value = b'{"id":"550e8400-e29b-41d4-a716-446655440000","received_at":"2026-10-30T00:00:00Z"}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        transport = Mock(return_value=response)
        client = ErrorReportClient(transport=transport)
        client.send(make_report(ValueError('test')))
        request = transport.call_args.args[0]
        self.assertEqual(request.method, 'POST')
        self.assertNotIn('X-mibuds-install-id', request.headers)
        response.read.return_value = b'{}'
        with self.assertRaises(DeliveryError):
            client.send(make_report(ValueError('test')))
        transport.side_effect = HTTPError('http://example', 429, '', {'Retry-After': '600'}, io.BytesIO())
        with self.assertRaises(DeliveryError) as raised:
            client.send(make_report(ValueError('test')))
        self.assertEqual(raised.exception.delay, 600)

    def test_durable_retries_capacity_expiration(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1000.0]
            client = Mock()
            client.send.side_effect = DeliveryError(True)
            queue = ReportQueue(directory=directory, client=client, clock=lambda: now[0])
            self.assertTrue(queue.enqueue(make_report(ValueError('test'))))
            client.send.assert_not_called()
            for delay in (60, 300, 1800, 7200):
                queue.process_due()
                record = json.loads(next(Path(directory).glob('*.json')).read_text())
                self.assertEqual(record['next'], now[0] + delay)
                now[0] += delay
                queue = ReportQueue(directory=directory, client=client, clock=lambda: now[0])
            queue.process_due()
            self.assertEqual(client.send.call_count, 5)
            self.assertEqual(list(Path(directory).glob('*.json')), [])
            for _ in range(20):
                self.assertTrue(queue.enqueue(make_report(ValueError('test'))))
            self.assertFalse(queue.enqueue(make_report(ValueError('full'))))
            now[0] += 7 * 86400
            self.assertTrue(queue.enqueue(make_report(ValueError('expired'))))

    def test_success_and_terminal_failure_delete_queue(self):
        for failure in (None, DeliveryError(False)):
            with tempfile.TemporaryDirectory() as directory:
                client, notify = Mock(), Mock()
                client.send.side_effect = failure
                queue = ReportQueue(directory=directory, client=client, notify=notify)
                queue.enqueue(make_report(ValueError('test')))
                queue.process_due()
                self.assertEqual(list(Path(directory).glob('*.json')), [])
                notify.assert_called_once_with('failed' if failure else 'sent')


if __name__ == '__main__':
    unittest.main()
