"""Settings card UI components."""

from typing import Callable, Optional

import flet as ft

from controllers.catalog.capabilities import DeviceCapabilities
from controllers.noise.protocol import noise_capabilities, noise_backend_enabled
from utils.app.i18n import t

from ...constants import (
    CARD_BORDER_RADIUS,
    COLOR_BG,
    COLOR_HOME_BORDER,
    COLOR_HOME_MUTED,
    COLOR_HOME_SELECTED,
    COLOR_HOME_SELECTED_BORDER,
)
from ...localization import refresh_translations
from ..home.controls import HomeControls
from ..home.latency import LowLatencyModeSettingItem
from ..home.noise import NoiseSettings
from ..shared.equalizer import EqualizerSettings
from .auto_mode import AutoModeSettingsAccordion
from .device_info import DeviceInfoSection
from .general import GeneralSection
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
        on_eq_action: Optional[Callable] = None,
        on_noise_action: Optional[Callable] = None,
    ):
        self._capabilities = DeviceCapabilities()
        self._connected = False
        self._compact_navigation = False
        self.latency_item = LowLatencyModeSettingItem(
            ft.Icons.SPORTS_ESPORTS, "blue_700", t("latency.title"),
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

        self.identity_section = DeviceInfoSection(on_check_device_identity)
        self.identity_item = self.identity_section.identity_item
        self.identity_image = self.identity_section.device_image
        self.identity_name = self.identity_section.name_text
        self.identity_model = self.identity_section.model_text
        self.identity_firmware = self.identity_section.firmware_text
        self._catalog_name = ""
        self._catalog_image = ""

        self.gestures = GestureSettings(on_gesture_refresh, on_gesture_assignment, on_update)
        self.equalizer = EqualizerSettings(on_eq_action, on_update)
        # Temporarily disable custom EQ while keeping presets available.
        self.equalizer.custom_supported = False
        self.noise = NoiseSettings(on_noise_action, on_update)
        self.home_controls_card = HomeControls(
            self.latency_item, self.noise.quick_controls, self.equalizer.quick_controls,
        )
        self.connection_panel = self.home_controls_card.connection_panel
        self.connection_card = self.home_controls_card.connection_card
        self.connected_controls = self.home_controls_card.connected_controls
        self.latency_card = self.home_controls_card.latency_card
        self.noise_card = self.home_controls_card.noise_card
        self.equalizer_card = self.home_controls_card.equalizer_card
        self.device_components = {"gestures": self.gestures, "eq": self.equalizer}
        general = GeneralSection(startup_enabled, on_startup_toggle, on_language_change)
        self.startup_item = general.startup_item
        self.language_selector = general.language_selector
        self._on_update = on_update
        self._selected_section = "general"
        self._sections = {
            "general": general,
            "auto": self.auto_settings,
            "gestures": self.gestures, "identity": self.identity_section,
        }
        self.gestures.toggle_button.visible = False
        self.gestures.controls[0].visible = False
        self.equalizer.toggle.visible = False
        self._menu = ft.Column(spacing=4, width=150)
        self._menu_items = {}
        self._section_title = ft.Text(size=17, weight="w600", color="white")
        self._section_surface = ft.Container(
            content=ft.Column(list(self._sections.values()), spacing=0,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            padding=0,
        )
        self._section_column = ft.Column([self._section_title, self._section_surface],
                                         spacing=14, expand=True,
                                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        items = ft.Row([self._menu, self._section_column], spacing=16,
                       vertical_alignment=ft.CrossAxisAlignment.START)

        super().__init__(
            content=ft.Column(
                [items], spacing=0, scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=COLOR_BG,
            border=ft.Border.all(1, COLOR_HOME_BORDER),
            border_radius=CARD_BORDER_RADIUS,
            padding=14
        )
        self._render_capabilities()

    def set_capabilities(self, capabilities):
        if capabilities != self._capabilities:
            self.gestures.set_connection(False)
            self.equalizer.set_connection(False)
            self.noise.set_connection(False)
        self._capabilities = capabilities
        self._render_capabilities()

    def _render_capabilities(self):
        caps = self._capabilities
        self._render_identity()
        self.latency_item.visible = self.auto_settings.visible = self._connected and caps.supports("latency")
        self.equalizer.quick_controls.visible = self._connected and caps.supports("eq")
        self.noise.capabilities = noise_capabilities(caps)
        self.noise.quick_controls.visible = self._connected and bool(self.noise.capabilities.modes)
        self.noise.set_connection(self._connected and bool(self.noise.capabilities.modes),
                                  noise_backend_enabled(caps))
        controls = []
        for card in (self.latency_card, self.noise_card, self.equalizer_card):
            card.visible = card.content.visible
            if card.visible:
                controls.append(card)
        self.connected_controls.controls = controls
        self.home_controls_card.visible = not self._connected or bool(controls)
        for feature, panel in self.device_components.items():
            panel.visible = self._connected and caps.supports(feature)
            panel.set_connection(panel.visible)
        self.refresh_connection_panel()
        self._available_sections = {
            "general": True, "auto": self._connected and caps.supports("latency"),
            "gestures": self._connected and caps.supports("gestures"),
            "identity": True,
        }
        if not self._available_sections[self._selected_section]:
            self._selected_section = "general"
        self._render_sections()

    def _render_sections(self):
        labels = {
            "general": (ft.Icons.SETTINGS_OUTLINED, "settings.general"),
            "auto": (ft.Icons.SPORTS_ESPORTS, "auto.title"),
            "gestures": (ft.Icons.TOUCH_APP, "gesture.title"),
            "identity": (ft.Icons.INFO_OUTLINE, "settings.device_info"),
        }
        self._section_title.value = t(labels[self._selected_section][1])
        self._menu.width = 52 if self._compact_navigation else 150
        for key, (icon, label) in labels.items():
            selected = key == self._selected_section
            if key not in self._menu_items:
                item = ft.Container(
                    content=ft.Row([ft.Icon(icon, size=20),
                                    ft.Text(size=12, expand=True, max_lines=2)], spacing=10),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=12), border_radius=12,
                    ink=True, on_click=lambda e, section=key: self.select_section(section),
                )
                self._menu_items[key] = item
                self._menu.controls.append(item)
            item = self._menu_items[key]
            item.visible = self._available_sections[key]
            item.tooltip = t(label)
            item.bgcolor = COLOR_HOME_SELECTED if selected else "transparent"
            item.gradient = (ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=[COLOR_HOME_SELECTED_BORDER, COLOR_HOME_SELECTED]) if selected else None)
            item.border = ft.Border.all(1, COLOR_HOME_SELECTED_BORDER if selected else "transparent")
            item.shadow = (ft.BoxShadow(blur_radius=10, color="#302463FF",
                                       offset=ft.Offset(0, 3)) if selected else None)
            row = item.content
            row.alignment = (ft.MainAxisAlignment.CENTER if self._compact_navigation
                             else ft.MainAxisAlignment.START)
            row.controls[0].color = "white" if selected else COLOR_HOME_MUTED
            text = row.controls[1]
            text.value = t(label)
            text.color = "white" if selected else COLOR_HOME_MUTED
            text.weight = "w600" if selected else "w400"
            text.visible = not self._compact_navigation
        for key, panel in self._sections.items():
            panel.visible = key == self._selected_section and self._available_sections[key]
        for key, panel in (("gestures", self.gestures),):
            active = key == self._selected_section and self._available_sections[key]
            if panel._opened != active:
                panel._toggle(None)

    def set_viewport_width(self, width: float) -> bool:
        compact = width < 500
        if compact == self._compact_navigation:
            return False
        self._compact_navigation = compact
        self._render_sections()
        return True

    def select_section(self, section):
        if not self._available_sections.get(section) or section == self._selected_section:
            return
        self._selected_section = section
        self._render_sections()
        self._on_update()

    def set_firmware_version(self, version: str | None) -> None:
        self.identity_section.set_firmware_version(version)

    def set_catalog_device(self, name: str, image_path: str = "") -> None:
        self._catalog_name, self._catalog_image = name, image_path
        self._render_identity()

    def _render_identity(self):
        caps = self._capabilities
        image = self._catalog_image if (self._connected and caps.name and
                 self._catalog_name.casefold() == caps.name.casefold()) else ""
        self.identity_section.set_device(
            caps.name if self._connected else "", caps.model if self._connected else "", image,
        )

    def update_connection_state(self, state: str, reason: str = "") -> None:
        """Show device controls only while the earbuds are connected."""
        self.connection_panel.update_connection_state(state, reason)
        connected = state == "connected"
        self._connected = connected
        if not connected:
            self.set_firmware_version(None)
        self._render_capabilities()

    def refresh_connection_panel(self):
        """Keep the home shell in place until the first EQ read succeeds."""
        waiting = self._connected and self._capabilities.supports("eq") and not self.equalizer.ready
        ready = self._connected and not waiting
        self.connection_card.visible = self.connection_panel.visible = not ready
        self.connected_controls.visible = ready
        if waiting:
            failed = self.equalizer.initial_read_failed
            self.connection_panel.update_connection_state(
                "failed" if failed else "loading", self.equalizer.status.value if failed else "")

    def retry_connection(self, reconnect):
        if self._connected and self._capabilities.supports("eq") and not self.equalizer.ready:
            self.equalizer.retry_initial_read()
            self.refresh_connection_panel()
            self._on_update()
        else:
            reconnect()

    def set_latency_mode(self, mode: str) -> None:
        self.latency_item.set_mode(mode)

    def set_device_identity_result(self, text: str, pending: bool = False) -> None:
        self.identity_section.set_lookup_result(text, pending)

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
