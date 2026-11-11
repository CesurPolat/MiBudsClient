"""Linux SDP tests use synthetic BlueZ records; no hardware or channel scans."""
import subprocess
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch

from controllers.bluetooth.connection import BluetoothConnection
from controllers.bluetooth.sdp import (
    ConnectionCancelled, PlatformBackend, SERVICE_UUIDS, _linux_record_channel,
)

ADDRESS = 'AA:BB:CC:DD:EE:FF'


def record(uuid, channel):
    return f'''<?xml version="1.0" encoding="UTF-8" ?>
<record>
 <attribute id="0x0001"><sequence><uuid value="{uuid}"/></sequence></attribute>
 <attribute id="0x0004"><sequence>
  <sequence><uuid value="0x0100"/></sequence>
  <sequence><uuid value="0x0003"/><uint8 value="{channel}"/></sequence>
 </sequence></attribute>
</record>'''.encode()


class LinuxRecordTests(unittest.TestCase):
    def test_exact_service_uses_own_channel_among_separate_xml_documents(self):
        output = b'Browsing ' + ADDRESS.encode() + b' ...\n' + record(SERVICE_UUIDS[2], 7) + record(SERVICE_UUIDS[0], 24)
        self.assertEqual(_linux_record_channel(output, SERVICE_UUIDS[0]), 24)
        self.assertEqual(_linux_record_channel(output, SERVICE_UUIDS[2]), 7)
        self.assertIsNone(_linux_record_channel(output, SERVICE_UUIDS[1]))

    def test_vendor_uuid_cannot_match_standard_spp_with_same_prefix(self):
        output = record('0x1101', 6)
        self.assertIsNone(_linux_record_channel(output, SERVICE_UUIDS[1]))
        self.assertEqual(_linux_record_channel(output, SERVICE_UUIDS[2]), 6)
        self.assertEqual(_linux_record_channel(record('0xFD2D', 24), SERVICE_UUIDS[0]), 24)

    def test_service_id_can_identify_exact_service(self):
        output = record(SERVICE_UUIDS[0], 24).replace(b'id="0x0001"', b'id="0x0003"')
        self.assertEqual(_linux_record_channel(output, SERVICE_UUIDS[0]), 24)

    def test_channel_cannot_leak_from_other_record_or_protocol(self):
        no_rfcomm = record(SERVICE_UUIDS[0], 24).replace(b'value="0x0003"', b'value="0x0008"')
        self.assertIsNone(_linux_record_channel(no_rfcomm + record(SERVICE_UUIDS[2], 6), SERVICE_UUIDS[0]))

    def test_invalid_and_ambiguous_channels_fail_discovery(self):
        for output in (
            record(SERVICE_UUIDS[0], 0), record(SERVICE_UUIDS[0], 31),
            record(SERVICE_UUIDS[0], 'not-a-number'),
            record(SERVICE_UUIDS[0], 6) + record(SERVICE_UUIDS[0], 24),
            record(SERVICE_UUIDS[0], 6).replace(b'uint8', b'uint16'),
            record(SERVICE_UUIDS[0], 6)[:-10],
        ):
            with self.subTest(output=output), self.assertRaises(OSError):
                _linux_record_channel(output, SERVICE_UUIDS[0])
        self.assertEqual(_linux_record_channel(record(SERVICE_UUIDS[0], 6) * 2, SERVICE_UUIDS[0]), 6)
        self.assertIsNone(_linux_record_channel(b'', SERVICE_UUIDS[0]))


class LinuxQueryTests(unittest.TestCase):
    def setUp(self):
        self.platform_patch = patch('controllers.bluetooth.sdp.sys.platform', 'linux')
        self.platform_patch.start()
        self.addCleanup(self.platform_patch.stop)
        self.process = MagicMock(returncode=0)
        self.process.__enter__.return_value = self.process
        self.process.poll.return_value = 0
        self.process.communicate.return_value = (record(SERVICE_UUIDS[0], 24), b'')
        context = patch('controllers.bluetooth.sdp.subprocess.Popen', return_value=self.process)
        self.popen = context.start()
        self.addCleanup(context.stop)
        self.cancel = threading.Event()

    def resolve(self, timeout=1):
        return PlatformBackend().resolve_rfcomm_channel(ADDRESS, SERVICE_UUIDS[0], timeout, self.cancel)

    def test_queries_only_selected_peer_with_bluez_and_records_linux_source(self):
        self.assertEqual(self.resolve(), 24)
        self.assertEqual(self.popen.call_args.args[0], ['sdptool', 'search', '--bdaddr', ADDRESS, '--xml', '0xfd2d'])
        self.assertNotIn('shell', self.popen.call_args.kwargs)
        self.process.kill.assert_not_called()
        backend = PlatformBackend()
        backend.create_rfcomm_socket = Mock(return_value=Mock())
        result = BluetoothConnection(backend).connect(ADDRESS, 'Redmi Buds 6 Play')
        self.assertEqual((result.channel, result.service_uuid, result.resolution_source),
                         (24, SERVICE_UUIDS[0], 'linux_sdp'))

    def test_vendor_service_browses_peer_without_collapsing_to_standard_spp(self):
        self.process.communicate.return_value = (record(SERVICE_UUIDS[1], 7), b'')
        result = PlatformBackend().resolve_rfcomm_channel(ADDRESS, SERVICE_UUIDS[1], 1, self.cancel)
        self.assertEqual(result, 7)
        self.assertEqual(self.popen.call_args.args[0], ['sdptool', 'browse', '--xml', ADDRESS])

    def test_missing_sdptool_has_actionable_error_and_6_play_retains_fallback(self):
        self.popen.side_effect = FileNotFoundError()
        with self.assertRaisesRegex(OSError, 'sdptool'):
            self.resolve()
        backend = PlatformBackend()
        backend.create_rfcomm_socket = Mock(return_value=Mock())
        result = BluetoothConnection(backend).connect(ADDRESS, 'Redmi Buds 6 Play')
        self.assertEqual((result.channel, result.service_uuid, result.resolution_source),
                         (6, None, 'profile_fallback'))

    def test_absent_service_returns_none_but_process_failure_is_reported(self):
        self.process.communicate.return_value = (record(SERVICE_UUIDS[2], 7), b'')
        self.assertIsNone(self.resolve())
        for code in (0, 1):
            self.process.returncode = code
            self.process.communicate.return_value = (b'', b'Failed to connect to SDP server')
            with self.assertRaisesRegex(OSError, 'SDP server'):
                self.resolve()

    def test_cancellation_kills_and_reaps_pending_query(self):
        self.process.poll.return_value = None
        calls = 0
        def communicate(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                self.cancel.set()
                raise subprocess.TimeoutExpired('sdptool', .05)
            return b'', b''
        self.process.communicate.side_effect = communicate
        with self.assertRaises(ConnectionCancelled):
            self.resolve()
        self.process.kill.assert_called_once()
        self.assertEqual(calls, 2)

    def test_timeout_kills_and_reaps_query(self):
        self.process.poll.return_value = None
        with patch('controllers.bluetooth.sdp.time.monotonic', side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                self.resolve()
        self.process.kill.assert_called_once()
        self.process.communicate.assert_called_once_with()

    def test_already_cancelled_or_expired_query_does_not_spawn_process(self):
        self.cancel.set()
        with self.assertRaises(ConnectionCancelled):
            self.resolve()
        self.cancel.clear()
        with self.assertRaises(TimeoutError):
            self.resolve(timeout=0)
        self.popen.assert_not_called()

    def test_invalid_address_or_uuid_does_not_spawn_process(self):
        for address, uuid in (('--help', SERVICE_UUIDS[0]), (ADDRESS, 'invalid')):
            with self.assertRaises(ValueError):
                PlatformBackend().resolve_rfcomm_channel(address, uuid, 1, self.cancel)
        self.popen.assert_not_called()
