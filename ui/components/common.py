"""Common UI components."""

import flet as ft

from utils.resource_manager import get_resource_path

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
    DEVICE_IMAGE_SIZE,
    DEVICE_IMAGE_PATH,
)


class StatusBar(ft.Text):
    """Status text display at the bottom of the app."""

    def __init__(self, initial_text: str = "Status: Starting..."):
        super().__init__(
            value=initial_text,
            color=COLOR_DISABLED,
            size=12
        )

    def update_status(self, text: str, color: str = COLOR_TEXT_PRIMARY) -> None:
        """Update the status text and color."""
        self.value = f"Status: {text}"
        self.color = color


class DeviceImage(ft.Container):
    """Device image with fallback icon."""

    def __init__(self, src: str = DEVICE_IMAGE_PATH):
        super().__init__(
            content=ft.Container(
                content=ft.Image(
                    src=get_resource_path(src),
                    width=DEVICE_IMAGE_SIZE,
                    height=DEVICE_IMAGE_SIZE,
                    fit="contain",
                    error_content=ft.Icon(ft.Icons.HEADSET, size=58, color="white10"),
                ),
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
                ft.Text(f"version {version}", color=COLOR_DISABLED, size=10),
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
