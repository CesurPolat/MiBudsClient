"""Device image, connection status, and battery summary card."""

from utils.i18n import t, render

import flet as ft

from ..constants import COLOR_BG
from .battery import BatteryPanel
from .common import DeviceImage


class DeviceStatusCard(ft.Container):
    """Keep the device summary layout and display updates together."""

    def __init__(self):
        self.battery_panel = BatteryPanel()
        self.status_bar = ft.Text(t("device_status.disconnected"), size=11, color="white")
        self.status_dot = ft.Container(width=7, height=7, border_radius=4, bgcolor="grey")
        self.status_row = ft.Row([self.status_dot, self.status_bar], spacing=6, tight=True,
                                 alignment=ft.MainAxisAlignment.CENTER,
                                 vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.device_image = DeviceImage()
        self.device_name = ft.Text(size=13, color="white", weight="w500", visible=False,
                                   text_align=ft.TextAlign.CENTER)
        self._battery_spacer = ft.Container(expand=True, visible=False)
        super().__init__(
            content=ft.Column(
                controls=[
                    self.device_image,
                    self.device_name,
                    self.status_row,
                    self._battery_spacer,
                    ft.Container(content=self.battery_panel,
                                 alignment=ft.Alignment.CENTER),
                ],
                spacing=5,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            bgcolor=COLOR_BG,
            border_radius=18,
        )

    def set_wide_layout(self, wide: bool) -> None:
        self._battery_spacer.visible = wide
        self.content.tight = not wide
        self.padding = ft.Padding.only(left=8, right=8, top=6, bottom=0 if wide else 6)

    def update_catalog_device(self, name: str, image_path: str = "") -> None:
        self.device_name.value = name
        self.device_name.visible = bool(name)
        self.device_image.set_catalog_image(image_path)

    def update_status(self, text: str, color: str = "white") -> None:
        # Operational messages must not replace the connection indicator.
        self.status_row.tooltip = render(text)

    def update_connection_state(self, state: str, reason: str = "") -> None:
        label, color = {
            "connected": ("connected", "green"),
            "connecting": ("connecting", "amber"),
            "failed": ("error", "orange"),
        }.get(state, ("disconnected", "grey"))
        self.status_bar.value = t("device_status." + label)
        self.status_dot.bgcolor = color
        self.status_row.tooltip = render(reason) if reason else None

    def update_battery(self, left: int, right: int, case: int, transient: bool = False) -> None:
        self.battery_panel.update_all(left, right, case)
