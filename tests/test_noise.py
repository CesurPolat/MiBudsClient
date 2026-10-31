import unittest
from unittest.mock import Mock

from controllers.bluetooth.capabilities import resolve_capabilities
from controllers.bluetooth.noise import (
    noise_capabilities, build_noise_mode, build_noise_level, build_noise_read,
    parse_noise_state, parse_noise_notification, NoiseState, VALIDATED_NOISE_MODELS,
)
from controllers.bluetooth.noise_transport import NoiseTransport
from controllers.bluetooth.rcsp import RcspPacket


class NoiseTests(unittest.TestCase):
    def test_frames(self):
        for mode in range(3):
            self.assertEqual(build_noise_mode(16, mode).hex(),
                             f"fedcbac4080004100204{mode:02x}ef")
        self.assertEqual(build_noise_level(16, 1, 2, (1, 0, 2)).hex(),
                         "fedcbac4f200061004000b0102ef")
        self.assertEqual(build_noise_read(16).hex(), "fedcbac4f3000310000bef")
        build_noise_level(1, 1, 19, tuple(range(20)))
        for value in (20, -1, True):
            with self.assertRaises(ValueError):
                build_noise_level(1, 1, value, tuple(range(20)))

    def test_catalog_order_and_gating(self):
        caps = noise_capabilities(resolve_capabilities("Redmi Buds 5 Pro"))
        self.assertEqual(caps.anc_levels, (1, 0, 2))
        self.assertEqual(noise_capabilities(resolve_capabilities("Redmi Buds 6 Play")).modes, ())
        self.assertFalse(VALIDATED_NOISE_MODELS)
        self.assertNotIn(2, noise_capabilities(resolve_capabilities("Xiaomi Buds 5")).modes)

    def test_records_and_notification(self):
        data = bytes.fromhex("03 00 07 01 05 00 0b fe fd aa")
        self.assertEqual(parse_noise_state(data), NoiseState(254, 253, b"\xaa"))
        packet = RcspPacket(0x87, 0xF4, b"\x10" + data)
        self.assertEqual(parse_noise_notification(packet), parse_noise_state(data))
        self.assertIsNone(parse_noise_notification(RcspPacket(7, 0xF4, b"\x01\x10" + data)))
        for invalid in ("03 00 0b 01", "04 00 0b 01", "00"):
            with self.assertRaises(ValueError):
                parse_noise_state(bytes.fromhex(invalid))

    def test_ack_readback(self):
        channel = Mock()
        channel.transaction.return_value.__enter__ = Mock()
        channel.transaction.return_value.__exit__ = Mock(return_value=False)
        channel.exchange.side_effect = [b"arbitrary ACK", bytes.fromhex("04 00 0b 02 00")]
        caps = noise_capabilities(resolve_capabilities("Redmi Buds 5 Pro"))
        # An ACK followed by a different reported mode is not a successful write.
        with self.assertRaisesRegex(ValueError, "readback"):
            NoiseTransport(channel).apply(caps, 7, 1)
        self.assertEqual([call.args[0] for call in channel.exchange.call_args_list], [8, 243])
