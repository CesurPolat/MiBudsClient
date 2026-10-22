"""Device image, connection status, and battery summary card."""

import flet as ft

from ..constants import COLOR_BG
from .battery import BatteryPanel
from .common import DeviceImage, StatusBar


class DeviceStatusCard(ft.Container):
    """Keep the device summary layout and display updates together."""

    def __init__(self):
        self.battery_panel = BatteryPanel()
        self.status_bar = StatusBar()
        self.status_bar.size = 11
        super().__init__(
            content=ft.Row(
                controls=[
                    DeviceImage(),
                    ft.Column(
                        controls=[self.status_bar, self.battery_panel],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            bgcolor=COLOR_BG,
            border_radius=18,
        )

    def update_status(self, text: str, color: str = "white") -> None:
        self.status_bar.update_status(text, color)

    def update_battery(self, left: int, right: int, case: int, transient: bool = False) -> None:
        self.battery_panel.update_all(left, right, case)
        if transient:
            self.update_status("Refreshing battery data...", "white")
        else:
            self.update_status("Battery data updated", "green")
