"""Main screen, settings screen, and their shared navigation layout."""

from utils.i18n import t

from typing import Callable

import flet as ft
from ui.localization import refresh_translations

from ..constants import APP_TITLE, APP_VERSION, GITHUB_URL
from .common import AppTitle, Spacer, Footer
from .device_status import DeviceStatusCard
from .settings_card import SettingsCard


class AppLayout(ft.Column):
    """Keep both screens mounted so callbacks and form state survive navigation."""

    def __init__(self, device_status_card: DeviceStatusCard,
                 settings_card: SettingsCard, on_update: Callable[[], None]):
        self._on_update = on_update
        self.title = AppTitle(APP_TITLE)
        transition = ft.Animation(280, ft.AnimationCurve.EASE_IN_OUT_CUBIC)
        self.home_content = ft.Container(
            content=ft.Column(
                controls=[device_status_card, settings_card.home_controls_card],
                spacing=16,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            opacity=1,
            offset=ft.Offset(0, 0),
            animate_opacity=transition,
            animate_offset=transition,
        )
        self.settings_content = ft.Container(
            content=settings_card,
            top=0,
            left=0,
            right=0,
            opacity=0,
            offset=ft.Offset(0.06, 0),
            ignore_interactions=True,
            animate_opacity=transition,
            animate_offset=transition,
        )
        self.page_content = ft.Stack(
            controls=[self.home_content, self.settings_content],
            fit=ft.StackFit.PASS_THROUGH,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self.back_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            icon_color="white",
            tooltip=t("nav.back"),
            visible=False,
            on_click=lambda _: self.show_settings(False),
        )
        self.settings_button = ft.IconButton(
            icon=ft.Icons.SETTINGS_OUTLINED,
            icon_color="white",
            tooltip=t("nav.settings"),
            on_click=lambda _: self.show_settings(True),
        )
        self.navigation_header = ft.Row(
            controls=[
                ft.Container(content=self.back_button, width=48),
                ft.Container(content=self.title, expand=True, alignment=ft.Alignment.CENTER),
                ft.Container(content=self.settings_button, width=48),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        super().__init__(
            controls=[
                self.navigation_header,
                Spacer(height=8),
                self.page_content,
                Spacer(height=5),
                Footer(APP_VERSION, GITHUB_URL),
            ],
            spacing=10,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def show_settings(self, open_settings: bool) -> None:
        # Only the active screen contributes to the Stack's natural height.
        # Keep the inactive screen mounted for callbacks and form state.
        for screen, active in ((self.home_content, not open_settings),
                               (self.settings_content, open_settings)):
            screen.top = None if active else 0
            screen.left = None if active else 0
            screen.right = None if active else 0
        self.home_content.opacity = 0 if open_settings else 1
        self.home_content.offset = ft.Offset(-0.06 if open_settings else 0, 0)
        self.home_content.ignore_interactions = open_settings
        self.settings_content.opacity = 1 if open_settings else 0
        self.settings_content.offset = ft.Offset(0 if open_settings else 0.06, 0)
        self.settings_content.ignore_interactions = not open_settings
        self.back_button.visible = open_settings
        self.settings_button.visible = not open_settings
        self.title.value = t("nav.settings") if open_settings else APP_TITLE
        self._on_update()

    def refresh_translations(self) -> None:
        refresh_translations(self)
