"""Transport tests with fake backends: these do not validate earbuds hardware."""
import threading
import unittest
from unittest.mock import Mock, patch

from controllers.bluetooth.connection import BluetoothConnection
from controllers.bluetooth.controller import BTController
from controllers.bluetooth.sdp import ConnectionCancelled, PlatformBackend, SERVICE_UUIDS


class ServiceConnectionTests(unittest.TestCase):
    def backend(self, channels):
        backend = Mock()
        backend.resolve_rfcomm_channel.side_effect = channels
        backend.create_rfcomm_socket.side_effect = lambda: Mock()
        return backend

    def test_same_service_different_peer_channels(self):
        for address, channel in (("AA:BB:CC:DD:EE:01", 6), ("AA:BB:CC:DD:EE:02", 24)):
            backend = self.backend([channel])
            connection = BluetoothConnection(backend)
            result = connection.connect(address)
            result.socket.connect.assert_called_once_with((address, channel))
            self.assertEqual(result.service_uuid, SERVICE_UUIDS[0])
            self.assertEqual(result.resolution_source, "windows_sdp")
            self.assertEqual(backend.resolve_rfcomm_channel.call_args.args[:2], (address, SERVICE_UUIDS[0]))
            connection.disconnect()
            result.socket.close.assert_called_once()
            self.assertIsNone(connection.result)

    def test_service_order_and_failed_socket_cleanup(self):
        backend = self.backend([24, None, 7])
        failed, good = Mock(), Mock()
        failed.connect.side_effect = OSError("refused")
        backend.create_rfcomm_socket.side_effect = [failed, good]
        result = BluetoothConnection(backend).connect("AA:BB:CC:DD:EE:FF")
        self.assertEqual([c.args[1] for c in backend.resolve_rfcomm_channel.call_args_list], list(SERVICE_UUIDS))
        failed.close.assert_called_once()
        self.assertEqual(result.service_uuid, SERVICE_UUIDS[2])
        self.assertEqual(result.channel, 7)

    def test_eof_preserves_metadata_until_controller_disconnect(self):
        connection = BluetoothConnection(self.backend([24]))
        result = connection.connect("AA:BB:CC:DD:EE:FF")
        result.socket.recv.return_value = b""
        self.assertEqual(connection.receive(), b"")
        result.socket.close.assert_not_called()
        self.assertTrue(connection.connected)
        self.assertIs(connection.result, result)
        connection.disconnect()
        result.socket.close.assert_called_once()
        self.assertFalse(connection.connected)
        self.assertIsNone(connection.result)

    def test_listener_reports_eof_before_closing_transport(self):
        connection = BluetoothConnection(self.backend([24]))
        result = connection.connect("AA:BB:CC:DD:EE:FF")
        result.socket.recv.return_value = b""

        def capture(error, action):
            self.assertIsInstance(error, ConnectionError)
            self.assertEqual(action, "bluetooth_receive")
            self.assertIs(connection.result, result)
            result.socket.close.assert_not_called()
            self.assertTrue(error.bluetooth_diagnostics["transport"])

        report = Mock(side_effect=capture)
        controller = BTController(error_callback=report)
        controller._connection = connection
        with patch("controllers.bluetooth.link.session.time.sleep",
                   side_effect=lambda _: setattr(controller, "_running", False)):
            controller.listen()
        report.assert_called_once()
        result.socket.close.assert_called_once()
        self.assertFalse(connection.connected)

    def test_unresolved_services_do_not_open_a_socket(self):
        for name in ("Redmi Buds 6 Play", "", "Redmi Buds 6", "Redmi Buds 6 Pro"):
            backend = self.backend([None] * 3)
            with self.assertRaises(ConnectionError):
                BluetoothConnection(backend).connect("AA:BB:CC:DD:EE:FF", name)
            backend.create_rfcomm_socket.assert_not_called()

    def test_failed_resolved_service_closes_socket(self):
        backend = self.backend([24, None, None])
        sock = Mock()
        sock.connect.side_effect = OSError("refused")
        backend.create_rfcomm_socket.side_effect = [sock]
        connection = BluetoothConnection(backend)
        with self.assertRaises(ConnectionError):
            connection.connect("AA:BB:CC:DD:EE:FF", "Redmi Buds 6 Play")
        sock.close.assert_called_once()
        self.assertFalse(connection.connected)

    def test_resolution_errors_fail_connection_and_unexpected_errors_propagate(self):
        backend = self.backend([TimeoutError("SDP timeout"), OSError("SDP failed"), None])
        with self.assertRaisesRegex(ConnectionError, "No usable RFCOMM service"):
            BluetoothConnection(backend).connect("AA:BB:CC:DD:EE:FF", "Redmi Buds 6 Play")
        backend = self.backend([RuntimeError("bug")])
        with self.assertRaisesRegex(RuntimeError, "bug"):
            BluetoothConnection(backend).connect("AA:BB:CC:DD:EE:FF", "Redmi Buds 6 Play")
        backend.create_rfcomm_socket.assert_not_called()

    def test_disconnect_cancels_pending_socket_without_publishing_success(self):
        backend = self.backend([24])
        sock = Mock()
        backend.create_rfcomm_socket.side_effect = [sock]
        connection = BluetoothConnection(backend)
        sock.connect.side_effect = lambda _: connection.disconnect()
        with self.assertRaises(ConnectionCancelled):
            connection.connect("AA:BB:CC:DD:EE:FF")
        self.assertFalse(connection.connected)
        self.assertIsNone(connection.result)
        self.assertTrue(sock.close.called)
        self.assertEqual(backend.resolve_rfcomm_channel.call_count, 1)

    def test_disconnect_cancels_pending_resolution(self):
        backend = self.backend([])
        connection = BluetoothConnection(backend)
        def resolve(address, uuid, timeout, cancel):
            connection.disconnect()
            raise ConnectionCancelled("cancelled")
        backend.resolve_rfcomm_channel.side_effect = resolve
        with self.assertRaises(ConnectionCancelled):
            connection.connect("AA:BB:CC:DD:EE:FF", "Redmi Buds 6 Play")
        backend.create_rfcomm_socket.assert_not_called()

    def test_total_budget_prevents_opening_socket(self):
        backend = self.backend([24])
        with patch("controllers.bluetooth.connection.time.monotonic", side_effect=[0, 0, 20, 20]):
            with self.assertRaises(TimeoutError):
                BluetoothConnection(backend).connect("AA:BB:CC:DD:EE:FF", timeout=1)
        backend.create_rfcomm_socket.assert_not_called()



class WindowsQueryLifecycleTests(unittest.TestCase):
    def test_windows_query_channel_missing_service_and_native_failure(self):
        for output, returncode, expected in ((b"24\r\n", 0, 24), (b"0\r\n", 0, None), (b"", 1, OSError)):
            process = Mock()
            process.__enter__ = Mock(return_value=process)
            process.__exit__ = Mock(return_value=False)
            process.poll.return_value = returncode
            process.returncode = returncode
            process.communicate.return_value = (output, b"native query failed" if returncode else b"")
            with patch("controllers.bluetooth.sdp.sys.platform", "win32"), patch("controllers.bluetooth.sdp.subprocess.Popen", return_value=process):
                if returncode:
                    with self.assertRaises(OSError):
                        PlatformBackend().resolve_rfcomm_channel("AA:BB:CC:DD:EE:FF", SERVICE_UUIDS[0], 1, threading.Event())
                else:
                    self.assertEqual(PlatformBackend().resolve_rfcomm_channel("AA:BB:CC:DD:EE:FF", SERVICE_UUIDS[0], 1, threading.Event()), expected)
            process.kill.assert_not_called()

    def test_timeout_and_cancel_kill_and_reap_native_query(self):
        for cancelled in (False, True):
            process = Mock()
            process.__enter__ = Mock(return_value=process)
            process.__exit__ = Mock(return_value=False)
            process.poll.return_value = None
            cancel = threading.Event()
            if cancelled:
                cancel.set()
            with patch("controllers.bluetooth.sdp.sys.platform", "win32"), patch("controllers.bluetooth.sdp.subprocess.Popen", return_value=process):
                with self.assertRaises(ConnectionCancelled if cancelled else TimeoutError):
                    PlatformBackend().resolve_rfcomm_channel("AA:BB:CC:DD:EE:FF", SERVICE_UUIDS[0], 0, cancel)
            process.kill.assert_called_once()
            process.communicate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
