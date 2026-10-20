"""Battery UI components."""

import flet as ft

from ..constants import (
    COLOR_DISABLED,
    COLOR_CHARGING,
    COLOR_BATTERY,
    COLOR_BATTERY_LOW,
    COLOR_CARD_BG,
    COLOR_TEXT_PRIMARY,
    BATTERY_UNKNOWN,
    BATTERY_CHARGING_OFFSET,
    BATTERY_LOW_THRESHOLD,
)


class BatteryIndicator(ft.Column):
    """Displays battery level for a single device (left/right/case)."""

    def __init__(self, label: str):
        self._label_text = ft.Text(label, color=COLOR_DISABLED, size=9, weight="w600")
        self._value_text = ft.Text("--", color=COLOR_TEXT_PRIMARY, size=15, weight="bold")

        super().__init__(
            controls=[self._label_text, self._value_text],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
            tight=True,
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


class BatteryPanel(ft.Container):
    """Panel displaying all three battery indicators."""

    def __init__(self):
        self._left = BatteryIndicator("LEFT")
        self._right = BatteryIndicator("RIGHT")
        self._case = BatteryIndicator("CASE")

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Container(content=self._left, expand=True, alignment=ft.Alignment.CENTER),
                    ft.Container(width=1, height=30, bgcolor="#2A313C"),
                    ft.Container(content=self._right, expand=True, alignment=ft.Alignment.CENTER),
                    ft.Container(width=1, height=30, bgcolor="#2A313C"),
                    ft.Container(content=self._case, expand=True, alignment=ft.Alignment.CENTER),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border_radius=16,
            bgcolor=COLOR_CARD_BG,
            border=ft.border.all(1, "#2D3542"),
            expand=True,
        )

    def update_all(self, left: int, right: int, case: int) -> None:
        """Update all battery indicators."""
        self._left.update_value(left)
        self._right.update_value(right)
        self._case.update_value(case)
