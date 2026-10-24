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
        self.device_image = DeviceImage()
        self.device_name = ft.Text(size=13, color="white", weight="w500", visible=False)
        super().__init__(
            content=ft.Row(
                controls=[
                    self.device_image,
                    ft.Column(
                        controls=[self.device_name, self.status_bar, self.battery_panel],
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

    def update_catalog_device(self, name: str, image_path: str = "") -> None:
        self.device_name.value = name
        self.device_name.visible = bool(name)
        self.device_image.set_catalog_image(image_path)

    def update_status(self, text: str, color: str = "white") -> None:
        self.status_bar.update_status(text, color)

    def update_battery(self, left: int, right: int, case: int, transient: bool = False) -> None:
        self.battery_panel.update_all(left, right, case)
        if transient:
            self.update_status("Refreshing battery data...", "white")
        else:
            self.update_status("Battery data updated", "green")
