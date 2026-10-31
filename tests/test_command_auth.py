"""Software-only auth verification: vectors, stream framing and mutual session."""
import socket
import unittest
from unittest.mock import Mock, patch

from controllers.bluetooth.auth_codec import encode_auth
from controllers.bluetooth.auth_session import AuthError, AuthPolicy, CommandAuthSession, profile_auth_policy
from controllers.bluetooth.connection import BluetoothConnection
from controllers.bluetooth.sdp import ConnectionCancelled
from controllers.bluetooth.rcsp import RcspStreamParser, build_identity_request
from controllers.bluetooth.safer_plus import challenge_response, _EXP, _LOG

VECTORS = (
    ("9762e8a1836d32cc4b7b8605c553545f", "f7fe2d0211bab715efe4c33ac740574d"),
    ("9ddc4d55a9f74b1c2df9d11a2762b281", "ac0512878403a24c87d1b6cb974061c9"),
    ("a979ae189a0c36bf973de72297ed1595", "7b09a3799fa3005472c2673c9c45e82b"),
    ("57990d37d3dad961ee7e6a092ba4f2ef", "6b21b2bdd693d3147ee9e6f41e46eb87"),
    ("60c881a805416aeeaa3a1e079d879568", "787748b987ecf34ab33464eaa78f44ba"),
)
A, ANSWER = map(bytes.fromhex, VECTORS[0])
B, B_ANSWER = map(bytes.fromhex, VECTORS[4])


class CipherTests(unittest.TestCase):
    def test_all_five_published_vectors(self):
        for challenge, answer in VECTORS:
            with self.subTest(challenge=challenge):
                self.assertEqual(challenge_response(bytes.fromhex(challenge)), bytes.fromhex(answer))

    def test_rejects_wrong_length_and_checks_tables(self):
        for length in (0, 15, 17, 32):
            with self.assertRaises(ValueError):
                challenge_response(bytes(length))
        self.assertEqual(_LOG[1], 0)
        self.assertEqual([_LOG[_EXP[x]] for x in range(256)], list(range(256)))


class AuthSessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.sent = []
        self.session = CommandAuthSession(self.sent.append, clock=lambda: self.now, random_bytes=lambda _: A)
        self.session.start()

    def answer(self, *, sequence=0, data=b"\x01" + ANSWER, status=0):
        return encode_auth(0x50, sequence, data, request=False, status=status)

    def challenge(self):
        return encode_auth(0x50, 16, b"\x01" + B)

    def result(self, result=0):
        return encode_auth(0x51, 17, bytes([1, result]))

    def test_mutual_flow_and_early_ack_cannot_make_ready(self):
        self.assertEqual(self.sent[0].hex(), "fedcbac45000120001" + A.hex() + "ef")
        self.session.feed(self.answer())
        self.session.feed(encode_auth(0x51, 1, b"\x01", request=False))
        self.assertFalse(self.session.authenticated)
        self.session.feed(self.challenge())
        self.assertEqual(self.sent[-1], encode_auth(0x50, 16, b"\x01" + B_ANSWER, request=False))
        self.assertFalse(self.session.authenticated)
        self.session.feed(self.result())
        self.assertTrue(self.session.authenticated)
        self.assertEqual(self.sent[-1], encode_auth(0x51, 17, b"\x01", request=False))
        self.assertFalse(self.session._pending)
        self.assertIsNone(self.session._expected)

    def test_fragmented_combined_frames_and_embedded_ef(self):
        stream = self.answer() + self.challenge() + self.result()
        for byte in stream:
            self.session.feed(bytes([byte]))
        self.assertTrue(self.session.authenticated)

    def test_coalesced_normal_frame_and_partial_tail_are_handed_off(self):
        normal = build_identity_request(99)
        output = self.session.feed(self.answer() + self.challenge() + self.result() + normal + normal[:9])
        parser = RcspStreamParser()
        self.assertEqual(len(parser.feed(b"".join(output))), 1)
        self.assertEqual(len(parser.feed(normal[9:])), 1)

    def test_wrong_sequence_or_target_is_ignored(self):
        self.session.feed(self.answer(sequence=13))
        wrong_target = bytearray(self.answer()); wrong_target[3] = 0
        self.session.feed(bytes(wrong_target))
        self.assertEqual(self.session.state, "waiting_answer")
        self.assertEqual(len(self.sent), 1)

    def test_wrong_answer_fails_and_sends_negative_result(self):
        with self.assertRaises(AuthError):
            self.session.feed(self.answer(data=b"\x01" + bytes(16)))
        self.assertEqual(self.sent[-1][-3:-1], b"\x01\x01")
        self.assertEqual(self.session.state, "failed")
        self.assertIsNone(self.session._expected)

    def test_peer_rejection_is_acked_but_never_ready(self):
        self.session.feed(self.answer() + self.challenge())
        with self.assertRaises(AuthError):
            self.session.feed(self.result(1))
        self.assertEqual(self.sent[-1], encode_auth(0x51, 17, b"\x01", request=False))
        self.assertFalse(self.session.authenticated)

    def test_wrong_version_length_and_status_fail(self):
        for data, status in ((b"\x02" + ANSWER, 0), (b"\x01" + ANSWER[:-1], 0), (b"\x01" + ANSWER, 1)):
            session = CommandAuthSession(lambda _: None, random_bytes=lambda _: A)
            session.start()
            with self.assertRaises(AuthError):
                session.feed(self.answer(data=data, status=status))

    def test_out_of_order_challenge_fails(self):
        with self.assertRaises(AuthError):
            self.session.feed(self.challenge())

    def test_request_retries_reuse_sequence_and_challenge_then_fail(self):
        first = self.sent[0]
        for now in (2, 4, 6):
            self.now = now
            self.session.tick()
        self.assertEqual(self.sent, [first] * 4)
        self.now = 8
        with self.assertRaises(AuthError):
            self.session.tick()

    def test_total_timeout_covers_missing_peer_result_after_ack(self):
        self.session.feed(self.answer() + encode_auth(0x51, 1, b"\x01", request=False) + self.challenge())
        self.now = 25
        with self.assertRaises(AuthError):
            self.session.tick()
        self.assertFalse(self.session.authenticated)

    def test_reset_clears_fragment_pending_and_auth_state(self):
        self.session.feed(self.answer()[:10])
        self.session.abort("disconnected")
        self.assertFalse(self.session._pending)
        self.assertIsNone(self.session._expected)
        self.session.reset()
        self.session.start()
        self.session.feed(self.answer(sequence=1))
        self.assertEqual(self.session.state, "waiting_challenge")


class AuthConnectionTests(unittest.TestCase):
    def backend(self):
        backend = Mock()
        backend.resolve_rfcomm_channel.return_value = 24
        self.sock = backend.create_rfcomm_socket.return_value
        return backend

    def test_explicit_auth_with_single_reader_and_normal_handoff(self):
        backend = self.backend()
        normal = build_identity_request(99)
        self.sock.recv.return_value = encode_auth(0x50, 0, b"\x01" + ANSWER, request=False) + encode_auth(0x50, 16, b"\x01" + B) + encode_auth(0x51, 17, b"\x01\x00") + normal
        connection = BluetoothConnection(backend)
        with patch('controllers.bluetooth.auth_session.secrets.token_bytes', return_value=A):
            connection.connect('AA:BB:CC:DD:EE:FF', session_policy='command_auth')
        self.assertTrue(connection.session_ready)
        self.assertTrue(connection.session_authenticated)
        self.assertEqual(connection.receive(), normal)
        self.assertEqual(self.sock.recv.call_count, 1)
        connection.disconnect()
        self.assertFalse(connection.session_authenticated)

    def test_auth_failure_closes_socket_without_trying_next_service(self):
        backend = self.backend()
        self.sock.recv.return_value = encode_auth(0x50, 0, b"\x01" + bytes(16), request=False)
        connection = BluetoothConnection(backend)
        with self.assertRaises(AuthError):
            connection.connect('AA:BB:CC:DD:EE:FF', 'Redmi Buds 6 Play', session_policy='command_auth')
        self.sock.close.assert_called_once()
        self.assertEqual(backend.resolve_rfcomm_channel.call_count, 1)
        self.assertIsNone(connection.result)
        self.assertFalse(connection.connected)

    def test_direct_does_not_read_or_authenticate(self):
        backend = self.backend()
        connection = BluetoothConnection(backend)
        connection.connect('AA:BB:CC:DD:EE:FF', 'Redmi Buds 6 Play', session_policy='direct')
        self.sock.recv.assert_not_called()
        self.sock.sendall.assert_not_called()
        self.assertTrue(connection.session_ready)
        self.assertFalse(connection.session_authenticated)

    def test_cancellation_closes_pending_auth_and_blocks_normal_io(self):
        backend = self.backend()
        connection = BluetoothConnection(backend)
        def receive(_):
            self.assertFalse(connection.connected)
            with self.assertRaises(ConnectionError):
                connection.send(build_identity_request(99))
            with self.assertRaises(ConnectionError):
                connection.receive()
            session = connection.auth_session
            connection.disconnect()
            self.assertFalse(session._pending)
            self.assertEqual(session.state, "failed")
            return b""
        self.sock.recv.side_effect = receive
        with self.assertRaises(ConnectionCancelled):
            connection.connect('AA:BB:CC:DD:EE:FF', session_policy='command_auth')
        self.assertIsNone(connection.auth_session)
        self.assertFalse(connection.session_ready)
        self.sock.close.assert_called_once()

    def test_command_auth_never_runs_on_other_service_or_unknown_fallback(self):
        for channels, name in (([None, 7], ''), ([None, None, None], 'Redmi Buds 6 Play')):
            backend = self.backend()
            backend.resolve_rfcomm_channel.side_effect = channels
            with self.assertRaises(AuthError):
                BluetoothConnection(backend).connect('AA:BB:CC:DD:EE:FF', name, session_policy='command_auth')
            self.sock.sendall.assert_not_called()
            self.sock.recv.assert_not_called()

    def test_6_play_sdp_failure_preserves_direct_profile_fallback(self):
        backend = self.backend()
        backend.resolve_rfcomm_channel.return_value = None
        connection = BluetoothConnection(backend)
        result = connection.connect('AA:BB:CC:DD:EE:FF', 'Redmi Buds 6 Play', session_policy=AuthPolicy.DIRECT)
        self.assertEqual(result.channel, 6)
        self.assertIsNone(result.service_uuid)
        self.assertTrue(connection.session_ready)
        self.assertFalse(connection.session_authenticated)
        self.sock.sendall.assert_not_called()

    def test_no_implicit_model_auth_and_raw_is_unsupported(self):
        self.assertEqual(profile_auth_policy('Redmi Buds 6 Play'), AuthPolicy.COMMAND)
        self.assertEqual(profile_auth_policy('Redmi Buds 5 Pro'), AuthPolicy.UNKNOWN)
        for policy in ('raw_auth', 'unknown'):
            backend = self.backend()
            with self.assertRaises(AuthError):
                BluetoothConnection(backend).connect('AA:BB:CC:DD:EE:FF', session_policy=policy)
            self.sock.recv.assert_not_called()
            self.sock.close.assert_called_once()

    def test_controller_supplies_explicit_or_model_policy(self):
        from controllers.bluetooth.controller import BTController
        for name, override, expected in (
            ('Redmi Buds 6 Play', None, AuthPolicy.COMMAND),
            ('Redmi Buds 5 Pro', None, AuthPolicy.UNKNOWN),
            ('Redmi Buds 5 Pro', 'command_auth', AuthPolicy.COMMAND),
            ('Redmi Buds 6 Play', 'direct', AuthPolicy.DIRECT),
        ):
            controller = BTController(bd_addr='AA:BB:CC:DD:EE:FF', auth_policy=override)
            controller._device_name = name
            controller._connection = Mock(connected=False)
            controller.on_connect_setup = Mock()
            self.assertTrue(controller.connect())
            self.assertEqual(controller._connection.connect.call_args.kwargs['session_policy'], expected)


if __name__ == '__main__':
    unittest.main()
