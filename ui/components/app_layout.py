"""Main screen, settings screen, and their shared navigation layout."""

from utils.i18n import t

from typing import Callable

import flet as ft
from ui.localization import refresh_translations

from ..constants import APP_VERSION, GITHUB_URL, WINDOW_WIDTH, PAGE_PADDING, HOME_WIDE_BREAKPOINT, HOME_CONTROLS_HEIGHT
from ..constants import FOOTER_HEIGHT, NAVIGATION_TRANSITION_MS
from .common import Spacer, Footer
from .device_status import DeviceStatusCard
from .settings_card import SettingsCard


class AppLayout(ft.Column):
    """Keep both screens mounted so callbacks and form state survive navigation."""

    def __init__(self, device_status_card: DeviceStatusCard,
                 settings_card: SettingsCard, on_update: Callable[[], None],
                 viewport_width: float | None = None,
                 on_settings_change: Callable[..., None] | None = None):
        self._on_update = on_update
        self._on_settings_change = on_settings_change
        self._device_status_card = device_status_card
        self._settings_card = settings_card
        self._home_controls = settings_card.home_controls_card
        self._connected_controls = settings_card.connected_controls
        self._wide = None
        self._settings_open = False
        self._navigation_pending = False
        self._pending_app_focus = False
        settings_card.latency_item.on_activation_app_click = self._open_game_app_settings
        transition = ft.Animation(NAVIGATION_TRANSITION_MS, ft.AnimationCurve.EASE_IN_OUT_CUBIC)
        self.home_content = ft.Container(
            offset=ft.Offset(0, 0),
            animate_offset=transition,
        )
        self.settings_content = ft.Container(
            content=settings_card,
            top=0,
            bottom=0,
            left=0,
            right=0,
            offset=ft.Offset(1, 0),
            ignore_interactions=True,
            animate_offset=transition,
            on_animation_end=self._finish_navigation,
        )
        # Home keeps its natural size; Settings fills the enlarged viewport.
        self.page_content = ft.Stack(
            controls=[self.home_content, self.settings_content],
            fit=ft.StackFit.PASS_THROUGH,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )

        self.navigation_button = ft.TextButton(
            icon=ft.Icons.SETTINGS_OUTLINED,
            content=ft.Text(t("nav.settings"), size=11),
            style=ft.ButtonStyle(color="white", padding=0, icon_size=18),
            tooltip=t("nav.settings"),
            on_click=lambda _: self.show_settings(not self._settings_open),
        )
        self.footer = Footer(APP_VERSION, GITHUB_URL, self.navigation_button)
        self.footer.height = FOOTER_HEIGHT

        super().__init__(
            controls=[
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
        device.expand = False
        controls.expand = 3 if wide else False
        # The controls determine the height; the device summary fills that area.
        self._settings_card.connection_card.height = HOME_CONTROLS_HEIGHT
        self._settings_card.connection_card.expand = False
        self._settings_card.connection_panel.height = None if wide else HOME_CONTROLS_HEIGHT - 12
        # Flex children distort the intrinsic height used by the shared row.
        # Measure the complete card stack, including its bottom padding.
        self._connected_controls.expand = False
        controls.content.tight = True
        self._connected_controls.alignment = ft.MainAxisAlignment.START
        if wide:
            device_slot = ft.Stack([
                ft.Container(content=device, top=0, bottom=0, left=0, right=0),
            ], expand=2)
            self.home_content.content = ft.Row(
                [device_slot, controls], spacing=8, intrinsic_height=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        else:
            self.home_content.content = ft.Column(
                [device, controls], spacing=8, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        return True

    def show_settings(self, open_settings: bool) -> None:
        if self._navigation_pending or open_settings == self._settings_open:
            return
        self._settings_open = open_settings
        self._navigation_pending = True
        self.navigation_button.disabled = True
        if not open_settings:
            # Keep Settings on screen while Home's natural height is restored.
            self.page_content.height = None
            if self._on_settings_change:
                self._on_settings_change(False, self._start_home_slide)
                self._on_update()
                return
        if self._on_settings_change:
            self._on_settings_change(open_settings)
        self._slide_to_screen(open_settings)

    def _start_home_slide(self) -> None:
        if self._navigation_pending and not self._settings_open:
            self._slide_to_screen(False)

    def _slide_to_screen(self, open_settings: bool) -> None:
        self.home_content.offset = ft.Offset(-1 if open_settings else 0, 0)
        self.home_content.ignore_interactions = open_settings
        self.settings_content.offset = ft.Offset(0 if open_settings else 1, 0)
        self.settings_content.ignore_interactions = not open_settings
        # Update the same footer button instead of inserting navigation controls;
        # the screen's widget position must stay stable for AnimatedSlide.
        label = t("nav.back" if open_settings else "nav.settings")
        self.navigation_button.icon = (
            ft.Icons.ARROW_BACK if open_settings else ft.Icons.SETTINGS_OUTLINED)
        self.navigation_button.content.value = label
        self.navigation_button.tooltip = label
        self._on_update()

    def _finish_navigation(self, _) -> None:
        if not self._navigation_pending:
            return
        self._navigation_pending = False
        self.navigation_button.disabled = False
        if self._settings_open:
            self.fit_settings_height()
        else:
            self.page_content.height = None
        self._on_update()
        if self._settings_open and self._pending_app_focus:
            self._pending_app_focus = False
            self.page.run_task(self._settings_card.auto_settings.focus_app_input)

    def _open_game_app_settings(self, app_id: str) -> None:
        if self._navigation_pending or not self._settings_card._available_sections.get("auto"):
            return
        self._settings_card.auto_settings.prefill_app(app_id)
        self._settings_card.select_section("auto")
        self._pending_app_focus = True
        self.show_settings(True)

    def fit_settings_height(self) -> bool:
        """Use the available client height, leaving room for the shared footer."""
        if self._navigation_pending or not self._settings_open or not self.page.height:
            return False
        height = max(1, self.page.height - 2 * PAGE_PADDING - 18 - FOOTER_HEIGHT)
        if self.page_content.height == height:
            return False
        self.page_content.height = height
        return True

    def refresh_translations(self) -> None:
        refresh_translations(self)
