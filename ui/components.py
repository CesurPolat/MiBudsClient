"""Reusable UI Components."""

import flet as ft
from typing import Callable, Optional

from utils.resource_manager import get_resource_path

from .constants import (
    COLOR_DISABLED, COLOR_CHARGING, COLOR_BATTERY, COLOR_CARD_BG,
    COLOR_TEXT_PRIMARY, COLOR_DIVIDER, BATTERY_UNKNOWN, BATTERY_CHARGING_OFFSET,
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


# ─────────────────────────────────────────────────────────────────────────────
# Settings Card
# ─────────────────────────────────────────────────────────────────────────────
class SettingsCard(ft.Container):
    """Card containing settings options."""
    
    def __init__(
        self,
        on_low_latency: Optional[Callable] = None,
        on_standard: Optional[Callable] = None,
        on_check_battery: Optional[Callable] = None
    ):
        items = ft.Column([
            SettingItem(
                ft.Icons.SPEED, "blue700", "Low Latency Mode (On)",
                on_click=on_low_latency
            ),
            ft.Divider(color=COLOR_DIVIDER, thickness=0.5),
            SettingItem(
                ft.Icons.TIMER, "blue800", "Standard Mode (Off)",
                on_click=on_standard
            ),
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
