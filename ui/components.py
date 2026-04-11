"""Reusable UI Components."""

import flet as ft
from typing import Callable, Optional

from utils.resource_manager import get_resource_path

from .constants import (
    COLOR_DISABLED, COLOR_CHARGING, COLOR_BATTERY, COLOR_BATTERY_LOW, COLOR_CARD_BG,
    COLOR_TEXT_PRIMARY, COLOR_DIVIDER, BATTERY_UNKNOWN, BATTERY_CHARGING_OFFSET,
    BATTERY_LOW_THRESHOLD,
    ICON_BUTTON_SIZE, DEVICE_IMAGE_SIZE, CARD_BORDER_RADIUS, ICON_BORDER_RADIUS, DEVICE_IMAGE_PATH,
    TRAY_ICON_PATH
)


# ─────────────────────────────────────────────────────────────────────────────
# Battery Indicator
# ─────────────────────────────────────────────────────────────────────────────
class BatteryIndicator(ft.Column):
    """Displays battery level for a single device (left/right/case)."""
    
    def __init__(self, label: str):
        self._label_text = ft.Text(label, color=COLOR_DISABLED, size=12)
        self._value_text = ft.Text("--", color=COLOR_TEXT_PRIMARY, size=16, weight="bold")
        
        super().__init__(
            controls=[self._label_text, self._value_text],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
    
    def update_value(self, raw_value: int) -> None:
        """Update the battery display with a raw value."""
        text, color = self._format_battery(raw_value)
        self._value_text.value = text
        self._value_text.color = color
    
    @staticmethod
    def _format_battery(val: int) -> tuple[str, str]:
        """Format battery value for display. Returns (text, color)."""
        if val == BATTERY_UNKNOWN:
            return "---", COLOR_DISABLED
        
        is_charging = val >= BATTERY_CHARGING_OFFSET
        actual_val = val - BATTERY_CHARGING_OFFSET if is_charging else val
        
        if actual_val > 100:
            return "---", COLOR_DISABLED
        
        text = f"%{actual_val}"
        if is_charging:
            return f"⚡ {text}", COLOR_CHARGING
        
        if actual_val <= BATTERY_LOW_THRESHOLD:
            return text, COLOR_BATTERY_LOW
        
        return text, COLOR_BATTERY


# ─────────────────────────────────────────────────────────────────────────────
# Battery Panel
# ─────────────────────────────────────────────────────────────────────────────
class BatteryPanel(ft.Row):
    """Panel displaying all three battery indicators."""
    
    def __init__(self):
        self._left = BatteryIndicator("LEFT")
        self._right = BatteryIndicator("RIGHT")
        self._case = BatteryIndicator("CASE")
        
        super().__init__(
            controls=[self._left, self._right, self._case],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY
        )
    
    def update_all(self, left: int, right: int, case: int) -> None:
        """Update all battery indicators."""
        self._left.update_value(left)
        self._right.update_value(right)
        self._case.update_value(case)


# ─────────────────────────────────────────────────────────────────────────────
# Settings Item
# ─────────────────────────────────────────────────────────────────────────────
class SettingItem(ft.ListTile):
    """A single settings menu item."""
    
    def __init__(
        self,
        icon: str,
        icon_bg_color: str,
        title: str,
        on_click: Optional[Callable] = None
    ):
        super().__init__(
            leading=ft.Container(
                content=ft.Icon(icon, color=COLOR_TEXT_PRIMARY),
                bgcolor=icon_bg_color,
                border_radius=ICON_BORDER_RADIUS,
                width=ICON_BUTTON_SIZE,
                height=ICON_BUTTON_SIZE
            ),
            title=ft.Text(title, color=COLOR_TEXT_PRIMARY, weight="medium"),
            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLOR_DISABLED),
            on_click=on_click
        )


class ToggleSettingItem(ft.ListTile):
    """A settings menu item with a toggle switch."""
    
    def __init__(
        self,
        icon: str,
        icon_bg_color: str,
        title: str,
        value: bool = False,
        on_change: Optional[Callable] = None
    ):
        self.switch = ft.Switch(
            value=value,
            on_change=on_change,
            active_color=COLOR_BATTERY
        )
        
        super().__init__(
            leading=ft.Container(
                content=ft.Icon(icon, color=COLOR_TEXT_PRIMARY),
                bgcolor=icon_bg_color,
                border_radius=ICON_BORDER_RADIUS,
                width=ICON_BUTTON_SIZE,
                height=ICON_BUTTON_SIZE
            ),
            title=ft.Text(title, color=COLOR_TEXT_PRIMARY, weight="medium"),
            trailing=self.switch,
            on_click=self._toggle_switch
        )

    def _toggle_switch(self, e):
        """Manually toggle the switch and trigger its on_change event."""
        self.switch.value = not self.switch.value
        self.switch.update()
        if self.switch.on_change:
            class MockEvent:
                def __init__(self, control):
                    self.control = control
            
            self.switch.on_change(MockEvent(self.switch))


class LowLatencyModeSettingItem(ft.Column):
    """Icon-based selector for Off/Auto/On low latency modes."""

    def __init__(
        self,
        icon: str,
        icon_bg_color: str,
        title: str,
        value: str = "off",
        on_change: Optional[Callable] = None,
    ):
        self._on_change = on_change
        self._value = value if value in {"off", "auto", "on"} else "off"
        self._mode_icons = {
            "off": ft.Icons.DO_NOT_DISTURB,
            "auto": ft.Icons.AUTORENEW,
            "on": ft.Icons.SPEED,
        }
        self._mode_labels = {
            "off": "Off",
            "auto": "Auto",
            "on": "On",
        }
        self._mode_buttons = {
            mode: ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(self._mode_icons[mode], size=16),
                        ft.Text(self._mode_labels[mode], size=13, weight="w500"),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                ),
                border_radius=10,
                padding=ft.padding.symmetric(vertical=10),
                alignment=ft.Alignment.CENTER,
                expand=True,
                ink=True,
                on_click=lambda e, selected_mode=mode: self._select_mode(selected_mode),
            )
            for mode in ("off", "auto", "on")
        }
        self._buttons_row = ft.Row(
            controls=list(self._mode_buttons.values()),
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=8,
        )

        super().__init__(
            controls=[
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(icon, color=COLOR_TEXT_PRIMARY),
                        bgcolor=icon_bg_color,
                        border_radius=ICON_BORDER_RADIUS,
                        width=ICON_BUTTON_SIZE,
                        height=ICON_BUTTON_SIZE,
                    ),
                    title=ft.Text(title, color=COLOR_TEXT_PRIMARY, weight="medium"),
                ),
                ft.Container(content=self._buttons_row, padding=ft.padding.only(left=12, right=12, bottom=8)),
            ],
            spacing=0,
        )
        self._apply_styles()

    @property
    def value(self) -> str:
        return self._value

    def _select_mode(self, mode: str) -> None:
        if mode not in self._mode_buttons or mode == self._value:
            return

        self._value = mode
        self._apply_styles()
        self.update()

        if self._on_change:
            class MockControl:
                def __init__(self, value: str):
                    self.value = value

            class MockEvent:
                def __init__(self, value: str):
                    self.control = MockControl(value)

            self._on_change(MockEvent(self._value))

    def set_mode(self, mode: str) -> None:
        normalized = (mode or "").strip().lower()
        if normalized not in self._mode_buttons:
            normalized = "off"
        self._value = normalized
        self._apply_styles()
        self.update()

    def _apply_styles(self) -> None:
        for mode, button in self._mode_buttons.items():
            selected = mode == self._value
            button.bgcolor = "#1976D2" if selected else "#2B2F3A"
            button.border = ft.border.all(
                1,
                "#4FC3F7" if selected else "#3B3F4A",
            )
            row = button.content
            if isinstance(row, ft.Row):
                for control in row.controls:
                    if isinstance(control, ft.Icon):
                        control.color = "white" if selected else COLOR_DISABLED
                    elif isinstance(control, ft.Text):
                        control.color = "white" if selected else COLOR_TEXT_PRIMARY


class PlatformExceptionEditor(ft.Column):
    """Editor for a single platform list."""

    def __init__(
        self,
        platform_key: str,
        label: str,
        placeholder: str,
        values: list[str],
        on_add: Optional[Callable[[str, str], None]] = None,
        on_remove: Optional[Callable[[str, str], None]] = None,
    ):
        self._platform_key = platform_key
        self._on_add = on_add
        self._on_remove = on_remove
        self._values = sorted({(value or "").strip().lower() for value in values if value and value.strip()})

        self._list_column = ft.Column(spacing=4)
        self._field = ft.TextField(
            hint_text=placeholder,
            dense=True,
            expand=True,
            on_submit=self._add_value,
        )

        self._editor_surface = ft.Container(
            content=ft.Row(
                controls=[
                    self._field,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Add",
                        on_click=self._add_value,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#151922",
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, "#2A303C"),
        )

        self._render_rows()
        content_column = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text(label, size=12, color=COLOR_TEXT_PRIMARY, weight="w600"),
                    padding=ft.padding.only(left=4, bottom=2),
                ),
                self._editor_surface,
                self._list_column,
            ],
            spacing=8,
        )
        super().__init__(
            controls=[
                ft.Container(
                    content=content_column,
                    padding=ft.padding.symmetric(horizontal=6, vertical=4),
                )
            ],
            spacing=0,
        )

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _add_value(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        if value in self._values:
            self._field.value = ""
            self._field.update()
            return

        self._values.append(value)
        self._values.sort()
        if self._on_add:
            self._on_add(self._platform_key, value)
        self._field.value = ""
        self._render_rows()
        self.update()

    def _remove_value(self, value: str):
        if value not in self._values:
            return
        self._values.remove(value)
        if self._on_remove:
            self._on_remove(self._platform_key, value)
        self._render_rows()
        self.update()

    def _render_rows(self):
        if not self._values:
            self._list_column.controls = [
                ft.Container(
                    content=ft.Text("No entries.", size=12, color=COLOR_DISABLED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    bgcolor="#12161E",
                    border_radius=12,
                    border=ft.border.all(1, "#2A303C"),
                )
            ]
            return

        self._list_column.controls = [
            ft.Container(
                content=ft.ListTile(
                    dense=True,
                    title=ft.Text(item, size=13, color=COLOR_TEXT_PRIMARY),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Remove",
                        icon_color=COLOR_DISABLED,
                        on_click=lambda e, name=item: self._remove_value(name),
                    ),
                ),
                bgcolor="#12161E",
                border_radius=12,
                padding=ft.padding.only(left=6, right=4),
                border=ft.border.all(1, "#2A303C"),
            )
            for item in self._values
        ]

    def set_values(self, values: list[str]) -> None:
        self._values = sorted({(value or "").strip().lower() for value in values if value and value.strip()})
        self._render_rows()
        self.update()


class AutoModeSettingsAccordion(ft.ExpansionTile):
    """Accordion for automatic mode per-app rule settings."""

    def __init__(
        self,
        exclusions_by_platform: dict[str, list[str]],
        inclusions_by_platform: dict[str, list[str]],
        active_platform: str,
        wait_until_app_close_enabled: bool = False,
        on_wait_until_app_close_change: Optional[Callable] = None,
        on_add_item: Optional[Callable[[str, str], None]] = None,
        on_add_include_item: Optional[Callable[[str, str], None]] = None,
        on_remove_item: Optional[Callable[[str, str], None]] = None,
        on_set_item_mode: Optional[Callable[[str, str, str], None]] = None,
    ):
        self._active_platform = active_platform if active_platform in {"windows", "linux"} else "windows"
        self._on_add_item = on_add_item
        self._on_add_include_item = on_add_include_item
        self._on_remove_item = on_remove_item
        self._on_set_item_mode = on_set_item_mode
        platform_text = "Windows" if self._active_platform == "windows" else "Linux"
        exclusions = exclusions_by_platform.get(self._active_platform, [])
        inclusions = inclusions_by_platform.get(self._active_platform, [])
        self._rules: dict[str, str] = {}
        for name in exclusions:
            cleaned = (name or "").strip().lower()
            if cleaned:
                self._rules[cleaned] = "exclude"
        for name in inclusions:
            cleaned = (name or "").strip().lower()
            if cleaned:
                self._rules[cleaned] = "include"

        self._list_column = ft.Column(spacing=6)
        self._field = ft.TextField(
            hint_text="example.exe" if self._active_platform == "windows" else "example-binary",
            dense=True,
            expand=True,
            on_submit=self._add_exclude,
        )

        self._editor_surface = ft.Container(
            content=ft.Row(
                controls=[
                    self._field,
                    ft.IconButton(
                        icon=ft.Icons.DO_NOT_DISTURB,
                        tooltip="Add as exclude",
                        icon_color="#FF8A80",
                        on_click=self._add_exclude,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                        tooltip="Add as include",
                        icon_color="#81C784",
                        on_click=self._add_include,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#151922",
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, "#2A303C"),
        )

        self.wait_toggle = ToggleSettingItem(
            ft.Icons.TIMER,
            "teal_700",
            "Wait until app closes",
            value=wait_until_app_close_enabled,
            on_change=on_wait_until_app_close_change,
        )

        label_suffix = "(.exe)" if self._active_platform == "windows" else "(executable names)"
        self._list_label = ft.Text(
            f"{platform_text} process list {label_suffix}",
            size=12,
            weight="w600",
            color=COLOR_TEXT_PRIMARY,
        )

        header_icon = ft.Container(
            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=18, color="#9BC7FF"),
            width=34,
            height=34,
            border_radius=12,
            alignment=ft.Alignment.CENTER,
            bgcolor="#1B2330",
            border=ft.border.all(1, "#2D3A4F"),
        )

        header_text = ft.Column(
            controls=[
                ft.Text(
                    "Automatic Mode Settings",
                    color=COLOR_TEXT_PRIMARY,
                    size=14,
                    weight="w600",
                ),
                ft.Text(
                    "Auto: fullscreen apps open Low Latency; includes force open, excludes skip.",
                    size=12,
                    color=COLOR_DISABLED,
                ),
            ],
            spacing=2,
            expand=True,
        )

        platform_chip = ft.Container(
            content=ft.Text(platform_text, size=11, weight="w600", color="#BFD7FF"),
            bgcolor="#1B2330",
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border=ft.border.all(1, "#2D3A4F"),
        )

        tile_border = ft.RoundedRectangleBorder(
            radius=18,
            side=ft.BorderSide(width=1, color="#2A303C"),
        )

        controls_column = ft.Column(
            controls=[
                self.wait_toggle,
                ft.Container(
                    content=ft.Text(
                        "When enabled, Low Latency stays active until the matched app closes.",
                        size=11,
                        color=COLOR_DISABLED,
                    ),
                    padding=ft.padding.only(left=14, right=10, bottom=2),
                ),
                ft.Divider(height=1, color="#24303D"),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._list_label,
                            self._editor_surface,
                            self._list_column,
                        ],
                        spacing=8,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                ),
            ],
            spacing=10,
        )

        self._render_rules()

        super().__init__(
            title=ft.Container(
                content=ft.Row(
                    controls=[header_icon, header_text], #, platform_chip
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=4, bottom=4),
            ),
            bgcolor="#10141B",
            collapsed_bgcolor="#10141B",
            shape=tile_border,
            collapsed_shape=tile_border,
            text_color=COLOR_TEXT_PRIMARY,
            collapsed_text_color=COLOR_TEXT_PRIMARY,
            icon_color="#9BC7FF",
            collapsed_icon_color="#9BC7FF",
            controls=[
                ft.Container(
                    content=controls_column,
                    padding=ft.padding.only(top=6, bottom=2),
                ),
            ],
        )

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _add_exclude(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        self._rules[value] = "exclude"
        if self._on_add_item:
            self._on_add_item(self._active_platform, value)
        self._field.value = ""
        self._render_rules()
        self.update()

    def _add_include(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        self._rules[value] = "include"
        if self._on_add_include_item:
            self._on_add_include_item(self._active_platform, value)
        self._field.value = ""
        self._render_rules()
        self.update()

    def _remove_rule(self, value: str) -> None:
        if value not in self._rules:
            return
        del self._rules[value]
        if self._on_remove_item:
            self._on_remove_item(self._active_platform, value)
        self._render_rules()
        self.update()

    def _set_rule_mode(self, value: str, mode: str) -> None:
        if value not in self._rules or mode not in {"exclude", "include"}:
            return
        if self._rules[value] == mode:
            return
        self._rules[value] = mode
        if self._on_set_item_mode:
            self._on_set_item_mode(self._active_platform, value, mode)
        self._render_rules()
        self.update()

    def _build_mode_chip(self, value: str, mode: str, selected: bool) -> ft.Container:
        return ft.Container(
            content=ft.Text(mode.capitalize(), size=11, weight="w600", color="white" if selected else COLOR_TEXT_PRIMARY),
            bgcolor="#1976D2" if selected else "#2B2F3A",
            border=ft.border.all(1, "#4FC3F7" if selected else "#3B3F4A"),
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            ink=True,
            on_click=lambda e, name=value, target_mode=mode: self._set_rule_mode(name, target_mode),
        )

    def _render_rules(self) -> None:
        if not self._rules:
            self._list_column.controls = [
                ft.Container(
                    content=ft.Text("No entries.", size=12, color=COLOR_DISABLED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    bgcolor="#12161E",
                    border_radius=12,
                    border=ft.border.all(1, "#2A303C"),
                )
            ]
            return

        controls = []
        for item in sorted(self._rules.keys()):
            mode = self._rules[item]
            row = ft.Row(
                controls=[
                    ft.Text(item, size=13, color=COLOR_TEXT_PRIMARY, expand=True),
                    self._build_mode_chip(item, "exclude", mode == "exclude"),
                    self._build_mode_chip(item, "include", mode == "include"),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Remove",
                        icon_color=COLOR_DISABLED,
                        on_click=lambda e, name=item: self._remove_rule(name),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            controls.append(
                ft.Container(
                    content=row,
                    bgcolor="#12161E",
                    border_radius=12,
                    padding=ft.padding.only(left=10, right=6, top=4, bottom=4),
                    border=ft.border.all(1, "#2A303C"),
                )
            )

        self._list_column.controls = controls

    def set_rules(self, platform: str, exclusions: list[str], inclusions: list[str]) -> None:
        target = (platform or "").strip().lower()
        if target == self._active_platform:
            self._rules = {}
            for name in exclusions:
                normalized = self._normalize(name)
                if normalized:
                    self._rules[normalized] = "exclude"
            for name in inclusions:
                normalized = self._normalize(name)
                if normalized:
                    self._rules[normalized] = "include"
            self._render_rules()
        self.update()

    def set_wait_until_app_close(self, enabled: bool) -> None:
        self.wait_toggle.switch.value = bool(enabled)
        self.wait_toggle.switch.update()


# ─────────────────────────────────────────────────────────────────────────────
# Settings Card
# ─────────────────────────────────────────────────────────────────────────────
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
    ):
        self.latency_item = LowLatencyModeSettingItem(
            ft.Icons.SPEED, "blue_700", "Low Latency Mode",
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
            ft.Icons.ROCKET_LAUNCH, "deep_orange_700", "Run at Startup",
            value=startup_enabled,
            on_change=on_startup_toggle
        )

        items = ft.Column([
            self.latency_item,
            self.auto_settings,
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            self.startup_item,
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            SettingItem(
                ft.Icons.REFRESH, "grey700", "Check Battery",
                on_click=on_check_battery
            ),
        ], spacing=0)

        
        super().__init__(
            content=items,
            bgcolor=COLOR_CARD_BG,
            border_radius=CARD_BORDER_RADIUS,
            padding=10
        )

    def set_latency_mode(self, mode: str) -> None:
        self.latency_item.set_mode(mode)

    def set_low_latency_rules(self, platform: str, exclusions: list[str], inclusions: list[str]) -> None:
        self.auto_settings.set_rules(platform, exclusions, inclusions)

    def set_wait_until_app_close(self, enabled: bool) -> None:
        self.auto_settings.set_wait_until_app_close(enabled)

    @property
    def startup_switch(self) -> ft.Switch:
        """Access the underlying switch for startup setting."""
        return self.startup_item.switch


# ─────────────────────────────────────────────────────────────────────────────
# Status Bar
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# Device Image
# ─────────────────────────────────────────────────────────────────────────────
class DeviceImage(ft.Image):
    """Device image with fallback icon."""
    
    def __init__(self, src: str = DEVICE_IMAGE_PATH):
        super().__init__(
            src=get_resource_path(src),
            width=DEVICE_IMAGE_SIZE,
            height=DEVICE_IMAGE_SIZE,
            error_content=ft.Icon(ft.Icons.HEADSET, size=100, color="white10")
        )


# ─────────────────────────────────────────────────────────────────────────────
# App Title
# ─────────────────────────────────────────────────────────────────────────────
class AppTitle(ft.Text):
    """Application title text."""
    
    def __init__(self, title: str):
        super().__init__(
            value=title,
            size=24,
            weight="bold",
            color=COLOR_TEXT_PRIMARY
        )


# ─────────────────────────────────────────────────────────────────────────────
# Spacer
# ─────────────────────────────────────────────────────────────────────────────
class Spacer(ft.Container):
    """Vertical spacing container."""
    
    def __init__(self, height: int = 20, expand: bool = False):
        super().__init__(height=height, expand=expand)


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
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
