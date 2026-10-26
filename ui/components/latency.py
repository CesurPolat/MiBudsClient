"""Latency UI components."""

from utils.i18n import t

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
    ICON_BUTTON_SIZE,
    ICON_BORDER_RADIUS,
)


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
            "off": t("latency.off"),
            "auto": t("latency.auto"),
            "on": t("latency.on"),
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
        # Re-selecting a mode retries a failed command. The controller skips
        # sends for modes it has already applied successfully.
        if mode not in self._mode_buttons:
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
