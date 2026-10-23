"""The startup reservation must remain exclusive until the UI listener is ready."""

import socket
import threading
import unittest
from unittest.mock import Mock, patch

from utils import single_instance


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.port = port
        self.patch = patch.object(single_instance, "SINGLE_INSTANCE_PORT", port)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(single_instance.release_instance_port)

    def test_reservation_is_held_before_listener_thread_starts(self):
        listener = single_instance.reserve_instance_port()
        self.assertIs(single_instance.reserve_instance_port(), listener)
        with socket.socket() as competitor:
            with self.assertRaises(OSError):
                competitor.bind(("127.0.0.1", self.port))

    def test_losing_startup_exits_and_sends_focus(self):
        # A separate startup won the bind after our original startup check.
        with socket.socket() as owner:
            owner.bind(("127.0.0.1", self.port))
            owner.listen(1)
            owner.settimeout(2)
            with self.assertRaises(SystemExit) as exited:
                single_instance.reserve_instance_port()
            self.assertEqual(exited.exception.code, 0)
            client, _ = owner.accept()
            with client:
                self.assertEqual(client.recv(1024), b"focus")

    def test_focus_sent_during_startup_is_delivered_when_ui_is_ready(self):
        single_instance.reserve_instance_port()
        with socket.create_connection(("127.0.0.1", self.port), timeout=1) as client:
            client.sendall(b"focus")
        focused = threading.Event()
        window = Mock()
        window.show.side_effect = focused.set
        single_instance.start_instance_listener(window)
        self.assertTrue(focused.wait(2))
        window.show.assert_called_once_with()

    def test_original_startup_check_exits_during_reserved_startup(self):
        single_instance.reserve_instance_port()
        with self.assertRaises(SystemExit) as exited:
            single_instance.check_for_existing_instance()
        self.assertEqual(exited.exception.code, 0)
        focused = threading.Event()
        window = Mock()
        window.show.side_effect = focused.set
        single_instance.start_instance_listener(window)
        self.assertTrue(focused.wait(2))
