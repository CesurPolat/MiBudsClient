"""Main screen, settings screen, and their shared navigation layout."""

from utils.i18n import t

from typing import Callable

import flet as ft
from ui.localization import refresh_translations

from ..constants import APP_VERSION, GITHUB_URL, WINDOW_WIDTH, PAGE_PADDING, HOME_WIDE_BREAKPOINT
from .common import AppTitle, Spacer, Footer
from .device_status import DeviceStatusCard
from .settings_card import SettingsCard


class AppLayout(ft.Column):
    """Keep both screens mounted so callbacks and form state survive navigation."""

    def __init__(self, device_status_card: DeviceStatusCard,
                 settings_card: SettingsCard, on_update: Callable[[], None],
                 viewport_width: float | None = None):
        self._on_update = on_update
        self._device_status_card = device_status_card
        self._settings_card = settings_card
        self._home_controls = settings_card.home_controls_card
        self._connected_controls = settings_card.connected_controls
        self._wide = None
        self._settings_open = False
        self.title = AppTitle(t("nav.settings"))
        self.title.visible = False
        transition = ft.Animation(450, ft.AnimationCurve.EASE_IN_OUT_CUBIC)
        self.home_content = ft.Container(
            offset=ft.Offset(0, 0),
            animate_offset=transition,
            on_animation_end=lambda e: self._finish_transition(False),
        )
        self.settings_content = ft.Container(
            content=settings_card,
            height=0,
            offset=ft.Offset(1, 0),
            ignore_interactions=True,
            animate_offset=transition,
            on_animation_end=lambda e: self._finish_transition(True),
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
        self.settings_button = ft.TextButton(
            icon=ft.Icons.SETTINGS_OUTLINED,
            content=ft.Text(t("nav.settings"), size=11),
            style=ft.ButtonStyle(color="white", padding=0, icon_size=18),
            tooltip=t("nav.settings"),
            on_click=lambda _: self.show_settings(True),
        )
        self.navigation_header = ft.Row(
            controls=[
                ft.Container(content=self.back_button, width=48),
                ft.Container(content=self.title, expand=True, alignment=ft.Alignment.CENTER),
                ft.Container(width=48),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            height=0,
        )
        self.header_spacer = Spacer(height=0)
        self.footer = Footer(APP_VERSION, GITHUB_URL, self.settings_button)

        super().__init__(
            controls=[
                self.navigation_header,
                self.header_spacer,
                ft.Container(content=self.page_content, border_radius=0,
                             clip_behavior=ft.ClipBehavior.HARD_EDGE),
                Spacer(height=18),
                self.footer,
            ],
            spacing=0,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.set_viewport_width(viewport_width)

    def set_viewport_width(self, width: float | None) -> bool:
        width = width if isinstance(width, (int, float)) else WINDOW_WIDTH
        settings_changed = self._settings_card.set_viewport_width(width)
        wide = width - 2 * PAGE_PADDING >= HOME_WIDE_BREAKPOINT
        if wide == self._wide:
            return settings_changed
        self._wide = wide
        device, controls = self._device_status_card, self._home_controls
        device.set_wide_layout(wide)
        device.expand = 2 if wide else False
        controls.expand = 3 if wide else False
        self._connected_controls.expand = wide
        self._connected_controls.alignment = (
            ft.MainAxisAlignment.SPACE_BETWEEN if wide else ft.MainAxisAlignment.START)
        if wide:
            self.home_content.content = ft.Row(
                [device, controls], spacing=8, intrinsic_height=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        else:
            self.home_content.content = ft.Column(
                [device, controls], spacing=8, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        return True

    def show_settings(self, open_settings: bool) -> None:
        self._settings_open = open_settings
        # Keep both controls in the same Stack layout so their animations survive.
        # The outgoing screen is collapsed after its animation completes.
        (self.settings_content if open_settings else self.home_content).height = None
        self.home_content.offset = ft.Offset(-1 if open_settings else 0, 0)
        self.home_content.ignore_interactions = open_settings
        self.settings_content.offset = ft.Offset(0 if open_settings else 1, 0)
        self.settings_content.ignore_interactions = not open_settings
        self.back_button.visible = open_settings
        # Flet removes invisible Column children from the Flutter widget list.
        # Keep header slots mounted so showing them cannot remount the screens
        # and reset AnimatedSlide to its destination before it can animate.
        self.navigation_header.height = None if open_settings else 0
        self.header_spacer.height = 24 if open_settings else 0
        self.settings_button.visible = not open_settings
        self.title.visible = open_settings
        self.title.value = t("nav.settings")
        self._on_update()

    def _finish_transition(self, is_settings: bool) -> None:
        if is_settings != self._settings_open:
            screen = self.settings_content if is_settings else self.home_content
            if screen.height != 0:
                screen.height = 0
                self._on_update()

    def refresh_translations(self) -> None:
        refresh_translations(self)
