"""Device information shown in Settings."""

import flet as ft

from utils.app.i18n import render, t

from ...constants import COLOR_DISABLED, COLOR_DIVIDER, COLOR_HOME_HALO, COLOR_HOME_SURFACE
from ..shared.common import DeviceImage
from ..shared.setting_items import SettingItem


class DeviceInfoSection(ft.Container):
    def __init__(self, on_check_device_identity):
        self._device_name = ""
        self._catalog_device = ("", "")
        self.identity_item = SettingItem(
            ft.Icons.INFO_OUTLINE, "blue_grey_700", t("identity.title"),
            on_click=on_check_device_identity,
        )
        self.identity_item.subtitle = ft.Text(
            t("identity.not_queried"), size=12, color=COLOR_DISABLED, selectable=True,
        )

        self.device_image = DeviceImage()
        self.device_image.width = self.device_image.height = 130
        self.device_image._image_control.width = self.device_image._image_control.height = 120
        self.device_image.content.gradient = ft.RadialGradient(
            colors=[COLOR_HOME_HALO, COLOR_HOME_SURFACE], radius=0.65,
        )
        self.name_text = ft.Text("\u2014", size=18, weight="w600", color="white",
                                 text_align=ft.TextAlign.CENTER)
        self.model_text = ft.Text("\u2014", size=13, color="white", selectable=True,
                                  expand=True, text_align=ft.TextAlign.END)
        self.firmware_text = ft.Text("\u2014", size=13, color="white", selectable=True)
        super().__init__(
            content=ft.Column(
                [
                    ft.Container(content=self.device_image, alignment=ft.Alignment.CENTER),
                    self.name_text,
                    ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
                    ft.Row([ft.Text(t("identity.model"), color=COLOR_DISABLED, size=12),
                            self.model_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text(t("identity.firmware"), color=COLOR_DISABLED, size=12),
                            self.firmware_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=6,
        )

    def set_device(self, name: str, model: str) -> None:
        self._device_name = name
        self.name_text.value = name or "\u2014"
        self.model_text.value = model or "\u2014"
        self._refresh_device_image()

    def set_catalog_device(self, name: str, image_path: str) -> None:
        self._catalog_device = (name, image_path)
        self._refresh_device_image()

    def _refresh_device_image(self) -> None:
        catalog_name, image_path = self._catalog_device
        matches = self._device_name and self._device_name.casefold() == catalog_name.casefold()
        self.device_image.set_catalog_image(image_path if matches else "")

    def set_firmware_version(self, version: str | None) -> None:
        self.firmware_text.value = version or "\u2014"

    def set_lookup_result(self, text: str, pending: bool) -> None:
        self.identity_item.subtitle.value = render(text)
        self.identity_item.disabled = pending
