"""Battery UI components."""

from utils.i18n import t

import flet as ft

from ..constants import (
    COLOR_DISABLED,
    COLOR_CHARGING,
    COLOR_BATTERY,
    COLOR_BATTERY_LOW,
    COLOR_HOME_BORDER,
    COLOR_HOME_MUTED,
    COLOR_HOME_SURFACE,
    COLOR_HOME_SURFACE_TOP,
    COLOR_HOME_BATTERY,
    COLOR_TEXT_PRIMARY,
    BATTERY_UNKNOWN,
    BATTERY_CHARGING_OFFSET,
    BATTERY_LOW_THRESHOLD,
)


class BatteryIndicator(ft.Column):
    """Displays battery level for a single device (left/right/case)."""

    def __init__(self, label: str):
        self._label_text = ft.Text(label, color=COLOR_HOME_MUTED, size=9, weight="w500",
                                   text_align=ft.TextAlign.CENTER)
        self._value_text = ft.Text("--", color=COLOR_TEXT_PRIMARY, size=13, weight="w600",
                                   no_wrap=True, text_align=ft.TextAlign.CENTER)
        self._battery_fill = ft.Container(
            left=3, top=4, width=0, height=8, border_radius=2,
            bgcolor=COLOR_HOME_BATTERY)
        self._battery_outline = ft.Container(
            left=0, top=1, width=26, height=14, border_radius=4,
            border=ft.Border.all(1, COLOR_HOME_MUTED))
        # Charging occupies the same icon slot, never the percentage's width.
        self._charging_icon = ft.Icon(ft.Icons.BOLT, size=13, color="white", opacity=0)
        battery_icon = ft.Stack([
            self._battery_outline,
            self._battery_fill,
            ft.Container(right=0, top=5, width=2, height=6,
                         border_radius=1, bgcolor=COLOR_HOME_MUTED),
            ft.Container(content=self._charging_icon, left=0, right=2, top=0, bottom=0,
                         alignment=ft.Alignment.CENTER),
        ], width=28, height=16)

        super().__init__(
            controls=[self._label_text, battery_icon, self._value_text],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=3,
            tight=True,
        )

    def update_value(self, raw_value: int) -> None:
        """Update the battery display with a raw value."""
        text, _ = self._format_battery(raw_value)
        actual = raw_value - BATTERY_CHARGING_OFFSET if raw_value >= BATTERY_CHARGING_OFFSET else raw_value
        known = raw_value != BATTERY_UNKNOWN and 0 <= actual <= 100
        charging = known and raw_value >= BATTERY_CHARGING_OFFSET
        self._value_text.value = f"%{actual}" if known else "---"
        self._value_text.color = COLOR_BATTERY_LOW if known and actual <= BATTERY_LOW_THRESHOLD and not charging else COLOR_TEXT_PRIMARY
        self._battery_fill.width = 20 * actual / 100 if known else 0
        self._battery_fill.bgcolor = COLOR_BATTERY_LOW if known and actual <= BATTERY_LOW_THRESHOLD and not charging else COLOR_HOME_BATTERY
        self._battery_outline.border = ft.Border.all(1, self._battery_fill.bgcolor if known else COLOR_HOME_MUTED)
        self._battery_outline.shadow = (ft.BoxShadow(
            blur_radius=6, color="#3387E6AA") if known and actual > BATTERY_LOW_THRESHOLD else None)
        self._charging_icon.opacity = 1 if charging else 0
        self.tooltip = text

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
            return f"⚡{text}", COLOR_CHARGING

        if actual_val <= BATTERY_LOW_THRESHOLD:
            return text, COLOR_BATTERY_LOW

        return text, COLOR_BATTERY


class BatteryPanel(ft.Container):
    """Panel displaying all three battery indicators."""

    def __init__(self):
        self._left = BatteryIndicator(t("battery.left"))
        self._right = BatteryIndicator(t("battery.right"))
        self._case = BatteryIndicator(t("battery.case"))

        super().__init__(
            content=ft.Row(
                controls=[
                    ft.Container(content=self._left, expand=True, alignment=ft.Alignment.CENTER),
                    ft.Container(width=1, height=36, bgcolor=COLOR_HOME_BORDER),
                    ft.Container(content=self._right, expand=True, alignment=ft.Alignment.CENTER),
                    ft.Container(width=1, height=36, bgcolor=COLOR_HOME_BORDER),
                    ft.Container(content=self._case, expand=True, alignment=ft.Alignment.CENTER),
                ],
                alignment=ft.MainAxisAlignment.START,
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            border_radius=16,
            bgcolor=COLOR_HOME_SURFACE,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=[COLOR_HOME_SURFACE_TOP, COLOR_HOME_SURFACE]),
            border=ft.border.all(1, COLOR_HOME_BORDER),
            expand=True,
        )

    def update_all(self, left: int, right: int, case: int) -> None:
        """Update all battery indicators."""
        self._left.update_value(left)
        self._right.update_value(right)
        self._case.update_value(case)
