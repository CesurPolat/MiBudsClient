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
    HOME_CONTROLS_HEIGHT,
)

from controllers.bluetooth.capabilities import DeviceCapabilities

from .auto_mode import AutoModeSettingsAccordion
from .connection import ConnectionPanel
from .common import DeviceImage
from .latency import LowLatencyModeSettingItem
from .setting_items import SettingItem, ToggleSettingItem
from .gestures import GestureSettings
from .equalizer import EqualizerSettings
from .noise import NoiseSettings
from controllers.bluetooth.noise import noise_capabilities, noise_backend_enabled


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

        self._catalog_name = ""
        self._catalog_image = ""
        self.identity_image = DeviceImage()
        self.identity_image.width = self.identity_image.height = 130
        self.identity_image._image_control.width = self.identity_image._image_control.height = 120
        self.identity_name = ft.Text("\u2014", size=18, weight="w600", color="white",
                                     text_align=ft.TextAlign.CENTER)
        self.identity_model = ft.Text("\u2014", size=13, color="white", selectable=True, expand=True, text_align=ft.TextAlign.END)
        self.identity_firmware = ft.Text("\u2014", size=13, color="white", selectable=True)
        self.identity_section = ft.Container(
            content=ft.Column([
                ft.Container(content=self.identity_image, alignment=ft.Alignment.CENTER),
                self.identity_name,
                ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
                ft.Row([ft.Text("Model", color=COLOR_DISABLED, size=12),
                        self.identity_model], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Firmware", color=COLOR_DISABLED, size=12),
                        self.identity_firmware], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=6,
        )

        self.connection_panel = ConnectionPanel()
        self.battery_item = SettingItem(ft.Icons.REFRESH, "grey700", t("battery.check"), on_click=on_check_battery)
        self.battery_item.dense = True
        self.battery_item.content_padding = ft.Padding.symmetric(horizontal=8)

        def home_card(control):
            return ft.Container(content=control, bgcolor=COLOR_CARD_BG,
                                border_radius=CARD_BORDER_RADIUS, padding=6)

        self.connection_card = home_card(self.connection_panel)
        self.connection_card.height = HOME_CONTROLS_HEIGHT
        self.connected_controls = ft.Column(
            spacing=8, visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.home_controls_card = ft.Container(
            content=ft.Column([
                self.connection_card,
                self.connected_controls,
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        )

        self.gestures = GestureSettings(on_gesture_refresh, on_gesture_assignment, on_update)
        self.equalizer = EqualizerSettings(on_eq_action, on_update)
        # Temporarily disable custom EQ while keeping presets available.
        self.equalizer.custom_supported = False
        self.latency_card = home_card(self.latency_item)
        self.equalizer_card = home_card(self.equalizer.quick_controls)
        self.battery_card = home_card(self.battery_item)
        self.noise = NoiseSettings(on_noise_action, on_update)
        self.device_components = {"gestures": self.gestures, "eq": self.equalizer}
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
        self._language_container = ft.Container(content=self.language_selector, padding=10)
        self._on_update = on_update
        self._selected_section = "general"
        self._sections = {
            "general": ft.Container(
                content=ft.Column([self.startup_item, ft.Divider(height=1, color=COLOR_DIVIDER),
                                   self._language_container], spacing=6),
                padding=0),
            "auto": self.auto_settings, "noise": self.noise,
            "gestures": self.gestures, "identity": self.identity_section,
        }
        self.gestures.toggle_button.visible = False
        self.gestures.controls[0].visible = False
        self.equalizer.toggle.visible = False
        self.noise.toggle.visible = False
        self._menu = ft.Column(spacing=4, width=150)
        self._menu_items = {}
        self._section_title = ft.Text(size=17, weight="w600", color="white")
        self._section_surface = ft.Container(
            content=ft.Column(list(self._sections.values()), spacing=0,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor="#151B24", border_radius=16, padding=12,
            border=ft.Border.all(1, "#293443"),
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
            bgcolor="#0E1218",
            border=ft.Border.all(1, "#27313D"),
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
        self.battery_item.visible = self._connected and caps.supports("battery")
        self.equalizer.quick_controls.visible = self._connected and caps.supports("eq")
        controls = []
        for card in (self.latency_card, self.equalizer_card, self.battery_card):
            card.visible = card.content.visible
            if card.visible:
                controls.append(card)
        self.connected_controls.controls = controls
        self.home_controls_card.visible = not self._connected or bool(controls)
        for feature, panel in self.device_components.items():
            panel.visible = self._connected and caps.supports(feature)
            panel.set_connection(panel.visible)
        self.noise.capabilities = noise_capabilities(caps)
        self.noise.set_connection(self._connected and noise_backend_enabled(caps))
        self.refresh_connection_panel()
        self._available_sections = {
            "general": True, "auto": self._connected and caps.supports("latency"),
            "noise": self._connected and noise_backend_enabled(caps),
            "gestures": self._connected and caps.supports("gestures"),
            "identity": True,
        }
        if not self._available_sections[self._selected_section]:
            self._selected_section = "general"
        self._render_sections()

    def _render_sections(self):
        labels = {
            "general": (ft.Icons.SETTINGS_OUTLINED, "settings.general"),
            "auto": (ft.Icons.AUTO_AWESOME, "auto.title"),
            "noise": (ft.Icons.HEADPHONES, "noise.title"),
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
            item.bgcolor = "#23364C" if selected else "transparent"
            item.border = ft.Border.all(1, "#436A91" if selected else "transparent")
            row = item.content
            row.alignment = (ft.MainAxisAlignment.CENTER if self._compact_navigation
                             else ft.MainAxisAlignment.START)
            row.controls[0].color = "#9BC7FF" if selected else "#AEBAC9"
            text = row.controls[1]
            text.value = t(label)
            text.color = "white" if selected else "#C4CDDA"
            text.weight = "w600" if selected else "w400"
            text.visible = not self._compact_navigation
        for key, panel in self._sections.items():
            panel.visible = key == self._selected_section and self._available_sections[key]
        for key, panel in (("noise", self.noise), ("gestures", self.gestures)):
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
        self.identity_firmware.value = version or "\u2014"

    def set_catalog_device(self, name: str, image_path: str = "") -> None:
        self._catalog_name, self._catalog_image = name, image_path
        self._render_identity()

    def _render_identity(self):
        caps = self._capabilities
        self.identity_name.value = caps.name if self._connected and caps.name else "\u2014"
        self.identity_model.value = caps.model if self._connected and caps.model else "\u2014"
        image = self._catalog_image if (self._connected and caps.name and
                 self._catalog_name.casefold() == caps.name.casefold()) else ""
        self.identity_image.set_catalog_image(image)

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
