"""Window restoration must stay usable on smaller displays."""

import asyncio
import subprocess
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import flet as ft

from ui.window_manager import WindowManager
from utils.window_geometry import fit_window_size
from utils import window_geometry


class WindowGeometryTests(unittest.TestCase):
    def test_default_window_uses_original_fixed_size_without_measurement(self):
        page = SimpleNamespace(
            window=ft.Window(), platform=ft.PagePlatform.WINDOWS, run_task=Mock(),
        )
        with patch("ui.window_manager.get_work_area_size") as work_area:
            manager = WindowManager(page)
        self.assertEqual((page.window.width, page.window.height), (550, 735))
        self.assertEqual((page.window.min_height, page.window.max_height), (735, 735))
        self.assertEqual((page.window.min_width, page.window.max_width), (550, 550))
        self.assertFalse(page.window.resizable)
        self.assertFalse(page.window.maximizable)
        manager.set_content_measurement(Mock())
        page.run_task.assert_not_called()
        work_area.assert_not_called()

    def test_linux_uses_current_desktop_work_area(self):
        output = (
            "_NET_CURRENT_DESKTOP(CARDINAL) = 1\n"
            "_NET_WORKAREA(CARDINAL) = 0, 0, 1920, 1040, 0, 0, 1280, 680\n"
        )
        with patch.object(window_geometry.sys, "platform", "linux"), patch.dict(
            window_geometry.os.environ, {"DISPLAY": ":0"}
        ), patch.object(window_geometry.subprocess, "run", return_value=SimpleNamespace(stdout=output)):
            self.assertEqual(window_geometry.get_work_area_size(), (1280, 680))

    def test_linux_missing_display_tool_is_nonfatal(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("xprop", 1)):
            with patch.object(window_geometry.sys, "platform", "linux"), patch.dict(
                window_geometry.os.environ, {"DISPLAY": ":0"}
            ), patch.object(window_geometry.subprocess, "run", side_effect=error):
                self.assertIsNone(window_geometry.get_work_area_size())

    def test_large_saved_window_fits_smaller_desktop(self):
        self.assertEqual(
            fit_window_size((1600, 1200), (420, 400), (1280, 720)),
            (1256, 696, 420, 400),
        )

    def test_minimum_also_fits_tiny_desktop(self):
        self.assertEqual(
            fit_window_size((550, 735), (420, 400), (400, 360)),
            (376, 336, 376, 336),
        )

    def test_unavailable_screen_keeps_valid_saved_size(self):
        self.assertEqual(
            fit_window_size((650, 800), (420, 400), None),
            (650, 800, 420, 400),
        )

    def test_content_height_includes_padding_and_native_title_bar(self):
        page = SimpleNamespace(window=ft.Window(), run_task=Mock(), height=704, update=Mock())
        with patch(
            "ui.window_manager.get_work_area_size", return_value=(1920, 1080)
        ):
            manager = WindowManager(page, auto_resize=True)
        # Only the PNG signature and IHDR dimensions are read by the fitter.
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + struct.pack(">II", 510, 450)
        measurement = SimpleNamespace(capture=AsyncMock(return_value=png))
        manager.set_content_measurement(measurement)
        asyncio.run(manager._fit_content_after_layout(manager._fit_revision))
        self.assertEqual(page.window.height, 521)
        self.assertEqual(page.window.width, 550)
        self.assertGreater(page.update.call_count, 1)

    def test_new_layout_cancels_an_in_flight_height_transition(self):
        page = SimpleNamespace(window=ft.Window(), run_task=Mock(), update=Mock())
        with patch("ui.window_manager.get_work_area_size", return_value=None):
            manager = WindowManager(page, auto_resize=True)
        heights = []

        def supersede_transition():
            heights.append(page.window.height)
            manager._fit_revision += 1

        page.update.side_effect = supersede_transition
        asyncio.run(manager._animate_height(500, manager._fit_revision))
        self.assertEqual(len(heights), 1)
        self.assertGreater(page.window.height, 500)

    def test_stale_measurement_and_maximized_window_are_ignored(self):
        page = SimpleNamespace(window=ft.Window(), run_task=Mock(), height=704, update=Mock())
        with patch("ui.window_manager.get_work_area_size", return_value=(1280, 720)):
            manager = WindowManager(page, auto_resize=True)
        measurement = SimpleNamespace(capture=AsyncMock())
        manager.set_content_measurement(measurement)
        asyncio.run(manager._fit_content_after_layout(0))
        page.window.maximized = True
        asyncio.run(manager._fit_content_after_layout(manager._fit_revision))
        measurement.capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
