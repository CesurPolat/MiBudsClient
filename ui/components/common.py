"""Common UI components."""

from utils.i18n import t, render

import flet as ft

from utils.resource_manager import get_resource_path

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
    DEVICE_IMAGE_SIZE,
)


class StatusBar(ft.Text):
    """Status text display at the bottom of the app."""

    def __init__(self, initial_text: str | None = None):
        super().__init__(
            value=render(initial_text) if initial_text is not None else t("status.starting"),
            color=COLOR_DISABLED,
            size=12
        )

    def update_status(self, text: str, color: str = COLOR_TEXT_PRIMARY) -> None:
        """Update the status text and color."""
        self.value = t("status.message", text=text)
        self.color = color


class DeviceImage(ft.Container):
    """Device image with fallback icon."""

    def __init__(self, src: str | None = None):
        self._image_control = ft.Image(
            src=get_resource_path(src) if src else "",
            width=DEVICE_IMAGE_SIZE,
            height=DEVICE_IMAGE_SIZE,
            fit="contain",
            error_content=ft.Icon(ft.Icons.HEADSET, size=58, color="white10"),
        )
        super().__init__(
            content=ft.Container(
                content=self._image_control if src else self._placeholder(),
                alignment=ft.Alignment.CENTER,
                border_radius=(DEVICE_IMAGE_SIZE + 4) // 2,
            ),
            width=DEVICE_IMAGE_SIZE + 12,
            height=DEVICE_IMAGE_SIZE + 12,
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.all(4),
            border_radius=(DEVICE_IMAGE_SIZE + 12) // 2,
            bgcolor=None,
        )

    def set_catalog_image(self, path: str) -> None:
        self._image_control.src = get_resource_path(path) if path else ""
        self.content.content = self._image_control if path else self._placeholder()

    @staticmethod
    def _placeholder() -> ft.Icon:
        return ft.Icon(ft.Icons.HEADSET, size=58, color="white10")


class AppTitle(ft.Text):
    """Application title text."""

    def __init__(self, title: str):
        super().__init__(
            value=title,
            size=24,
            weight="bold",
            color=COLOR_TEXT_PRIMARY
        )


class Spacer(ft.Container):
    """Vertical spacing container."""

    def __init__(self, height: int = 20, expand: bool = False):
        super().__init__(height=height, expand=expand)


class Footer(ft.Column):
    """Footer containing version and GitHub link."""

    def __init__(self, version: str, github_url: str):
        super().__init__(
            controls=[
                ft.Text(t("footer.version", version=version), color=COLOR_DISABLED, size=10),
                ft.TextButton(
                    content=ft.Text(
                        github_url.replace("https://", ""),
                        color=COLOR_DISABLED,
                        size=10,
                        italic=True
                    ),
                    url=github_url,
                    style=ft.ButtonStyle(padding=0)
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0
        )
