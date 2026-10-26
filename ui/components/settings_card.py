"""Settings card UI components."""

from utils.i18n import t, render

import flet as ft
from ui.localization import refresh_translations
from utils.i18n import LANGUAGES
from utils.user_preferences import get_language_preference
from typing import Callable, Optional

from ..constants import (
    COLOR_CARD_BG,
    COLOR_DIVIDER,
    CARD_BORDER_RADIUS,
    COLOR_DISABLED,
)

from .auto_mode import AutoModeSettingsAccordion
from .connection import ConnectionPanel
from .latency import LowLatencyModeSettingItem
from .setting_items import SettingItem, ToggleSettingItem
from .gestures import GestureSettings


class SettingsCard(ft.Container):
    """Card containing settings options."""

    def __init__(
        self,
        on_low_latency_mode_change: Optional[Callable] = None,
        on_add_low_latency_list_item: Optional[Callable[[str, str], None]] = None,
        on_remove_low_latency_list_item: Optional[Callable[[str, str], None]] = None,
        on_set_low_latency_item_mode: Optional[Callable[[str, str, str], None]] = None,
        on_add_low_latency_include_item: Optional[Callable[[str, str], None]] = None,
        on_wait_until_app_close_change: Optional[Callable] = None,
        on_check_battery: Optional[Callable] = None,
        on_startup_toggle: Optional[Callable] = None,
        startup_enabled: bool = False,
        low_latency_mode: str = "off",
        active_platform: str = "windows",
        low_latency_exclusions_by_platform: Optional[dict[str, list[str]]] = None,
        low_latency_inclusions_by_platform: Optional[dict[str, list[str]]] = None,
        wait_until_app_close_enabled: bool = False,
        on_check_device_identity: Optional[Callable] = None,
        on_gesture_refresh: Optional[Callable] = None,
        on_gesture_assignment: Optional[Callable] = None,
        on_update: Callable = lambda: None,
        on_language_change: Optional[Callable] = None,
    ):
        self.latency_item = LowLatencyModeSettingItem(
            ft.Icons.SPEED, "blue_700", t("latency.title"),
            value=low_latency_mode,
            on_change=on_low_latency_mode_change,
        )

        self.auto_settings = AutoModeSettingsAccordion(
            exclusions_by_platform=low_latency_exclusions_by_platform or {},
            inclusions_by_platform=low_latency_inclusions_by_platform or {},
            active_platform=active_platform,
            wait_until_app_close_enabled=wait_until_app_close_enabled,
            on_wait_until_app_close_change=on_wait_until_app_close_change,
            on_add_item=on_add_low_latency_list_item,
            on_add_include_item=on_add_low_latency_include_item,
            on_remove_item=on_remove_low_latency_list_item,
            on_set_item_mode=on_set_low_latency_item_mode,
        )

        self.startup_item = ToggleSettingItem(
            ft.Icons.ROCKET_LAUNCH, "deep_orange_700", t("startup.title"),
            value=startup_enabled,
            on_change=on_startup_toggle
        )

        self.identity_item = SettingItem(
            ft.Icons.INFO_OUTLINE, "blue_grey_700", t("identity.title"),
            on_click=on_check_device_identity,
        )
        self.identity_item.subtitle = ft.Text(
            t("identity.not_queried"), size=12, color=COLOR_DISABLED, selectable=True,
        )

        self.connection_panel = ConnectionPanel()
        self.connected_controls = ft.Column([
                self.latency_item,
                self.auto_settings,
                ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
                SettingItem(
                    ft.Icons.REFRESH, "grey700", t("battery.check"),
                    on_click=on_check_battery,
                ),
            ], spacing=0, visible=False)
        self.home_controls_card = ft.Container(
            content=ft.Column([
                self.connection_panel,
                self.connected_controls,
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=COLOR_CARD_BG,
            border_radius=CARD_BORDER_RADIUS,
            padding=10,
        )

        self.gestures = GestureSettings(on_gesture_refresh, on_gesture_assignment, on_update)
        self.language_selector = ft.Dropdown(
            label=t("language.title"),
            value=get_language_preference(),
            options=[ft.dropdown.Option("system", t("language.system"))] + [
                ft.dropdown.Option(code, name) for code, name in LANGUAGES.items()
            ],
            on_select=on_language_change,
            color="white",
            filled=True,
            expand=True,
        )
        items = ft.Column([
            self.startup_item,
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            ft.Container(content=self.language_selector, padding=10),
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            self.gestures,
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            self.identity_item,
        ], spacing=0)


        super().__init__(
            content=items,
            bgcolor=COLOR_CARD_BG,
            border_radius=CARD_BORDER_RADIUS,
            padding=10
        )

    def update_connection_state(self, state: str, reason: str = "") -> None:
        """Show device controls only while the earbuds are connected."""
        self.connection_panel.update_connection_state(state, reason)
        connected = state == "connected"
        self.connection_panel.visible = not connected
        self.connected_controls.visible = connected
        self.gestures.set_connection(connected)

    def set_latency_mode(self, mode: str) -> None:
        self.latency_item.set_mode(mode)

    def set_device_identity_result(self, text: str, pending: bool = False) -> None:
        self.identity_item.subtitle.value = render(text)
        self.identity_item.disabled = pending

    def set_low_latency_rules(self, platform: str, exclusions: list[str], inclusions: list[str]) -> None:
        self.auto_settings.set_rules(platform, exclusions, inclusions)

    def set_wait_until_app_close(self, enabled: bool) -> None:
        self.auto_settings.set_wait_until_app_close(enabled)

    @property
    def startup_switch(self) -> ft.Switch:
        """Access the underlying switch for startup setting."""
        return self.startup_item.switch

    def refresh_translations(self) -> None:
        refresh_translations(self)
        refresh_translations(self.home_controls_card)
