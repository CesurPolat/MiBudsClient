"""Background update notifications respect the existing update preferences."""

import unittest
from unittest.mock import Mock, patch

from utils.updater import start_update_check


class BackgroundUpdateCheckTests(unittest.TestCase):
    def test_callback_only_receives_available_unsuppressed_versions(self):
        for result, allowed, expected in (
            ((True, "v1.2.3"), True, True),
            ((True, "v1.2.3"), False, False),
            ((False, None), True, False),
            ((True, None), True, False),
        ):
            with self.subTest(result=result, allowed=allowed), patch(
                "utils.updater.threading.Thread",
            ) as thread, patch("utils.updater.time.sleep") as sleep, patch(
                "utils.updater.check_for_updates", return_value=result,
            ) as check, patch(
                "utils.updater.should_show_update_notification", return_value=allowed,
            ) as preference:
                callback = Mock()
                worker = start_update_check(callback)
                self.assertIs(worker, thread.return_value)
                self.assertTrue(thread.call_args.kwargs["daemon"])
                worker.start.assert_called_once_with()
                check.assert_not_called()
                thread.call_args.kwargs["target"]()
                sleep.assert_called_once_with(3)
                check.assert_called_once_with()
                if expected:
                    callback.assert_called_once_with("v1.2.3")
                else:
                    callback.assert_not_called()
                if result[0] and result[1]:
                    preference.assert_called_once_with(result[1])
                else:
                    preference.assert_not_called()


if __name__ == "__main__":
    unittest.main()
