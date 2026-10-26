"""The app's melodies remain independent of silent OS notifications."""

import unittest
from unittest.mock import Mock, patch

from controllers.device.battery_updates import BatteryUpdates


class BatteryUpdatesTests(unittest.TestCase):
    def test_refresh_messages_and_original_charging_transition_melodies(self):
        publish = Mock()
        updates = BatteryUpdates(publish)
        with patch("controllers.device.battery_updates.time.sleep"), patch(
            "controllers.device.battery_updates.play_tones",
        ) as play:
            updates.update(60, 70, 255)
            play.assert_not_called()
            updates.update(188, 70, 255)
            play.assert_called_once_with([(880, 80), (1175, 90), (1568, 120)])
            updates.update(188, 70, 255)
            self.assertEqual(play.call_count, 1)
            updates.update(60, 70, 255)
            play.assert_called_with([(1568, 80), (1175, 90), (880, 120)])
            updates.update(255, 255, 255)
            updates.update(188, 198, 255)
            self.assertEqual(play.call_count, 2)
        messages = [call.args[0] for call in publish.call_args_list]
        self.assertTrue(all(message["transient"] and message["left"] == 255 for message in messages[::2]))
        self.assertTrue(all(not message["transient"] for message in messages[1::2]))
        self.assertEqual(messages[-1]["left"], 188)
        self.assertEqual(messages[-1]["right"], 198)

    def test_right_side_melody_and_invalid_values_do_not_create_false_transitions(self):
        updates = BatteryUpdates(Mock())
        with patch("controllers.device.battery_updates.time.sleep"), patch(
            "controllers.device.battery_updates.play_tones",
        ) as play:
            updates.update(60, 70, 255)
            updates.update(60, 198, 255)
            play.assert_called_once_with([(880, 80), (1175, 90), (1568, 120)])
            updates.update(60, 70, 255)
            play.assert_called_with([(1568, 80), (1175, 90), (880, 120)])
            for invalid in (255, 101, 229, None):
                updates.update(invalid, invalid, 255)
                updates.update(188, 198, 255)
            self.assertEqual(play.call_count, 2)
