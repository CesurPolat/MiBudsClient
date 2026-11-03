"""Latency UI components."""

from utils.i18n import t

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
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
                content=ft.Column(
                    controls=[
                        ft.Icon(self._mode_icons[mode], size=20),
                        ft.Text(self._mode_labels[mode], size=12, weight="w500",
                                text_align=ft.TextAlign.CENTER),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    spacing=4,
                ),
                border_radius=10,
                padding=ft.padding.symmetric(vertical=8),
                alignment=ft.Alignment.CENTER,
                expand=True,
                ink=True,
                on_click=lambda e, selected_mode=mode: self._select_mode(selected_mode),
            )
            for mode in ("off", "auto", "on")
        }
        self._ping_mode = None
        self._mode_feedback = {
            mode: ft.Container(
                content=button, expand=True, padding=2, border_radius=14,
                border=ft.Border.all(1, "transparent"),
                animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
                on_animation_end=lambda e, selected_mode=mode: self._clear_ping(selected_mode),
            )
            for mode, button in self._mode_buttons.items()
        }
        self._buttons_row = ft.Row(
            controls=list(self._mode_feedback.values()),
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=8,
        )

        super().__init__(
            controls=[
                ft.ListTile(
                    dense=True, min_height=44,
                    content_padding=ft.Padding.symmetric(horizontal=8),
                    leading=ft.Container(
                        content=ft.Icon(icon, size=20, color=COLOR_TEXT_PRIMARY),
                        bgcolor=icon_bg_color,
                        border_radius=ICON_BORDER_RADIUS,
                        width=32,
                        height=32,
                    ),
                    title=ft.Text(title, size=14, color=COLOR_TEXT_PRIMARY, weight="medium"),
                ),
                ft.Container(content=self._buttons_row, padding=ft.Padding.only(left=8, right=8, bottom=6)),
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
        self._ping_mode = mode
        for key, feedback in self._mode_feedback.items():
            feedback.border = ft.Border.all(1, "#664FC3F7" if key == mode else "transparent")
        self.update()

        if self._on_change:
            class MockControl:
                def __init__(self, value: str):
                    self.value = value

            class MockEvent:
                def __init__(self, value: str):
                    self.control = MockControl(value)

            self._on_change(MockEvent(self._value))

    def _clear_ping(self, mode: str) -> None:
        if self._ping_mode != mode:
            return
        self._ping_mode = None
        self._mode_feedback[mode].border = ft.Border.all(1, "transparent")
        try:
            self.page
        except RuntimeError:
            return  # A connection change can detach the selector during the ping.
        self.update()

    def set_mode(self, mode: str) -> None:
        normalized = (mode or "").strip().lower()
        if normalized not in self._mode_buttons:
            normalized = "off"
        self._value = normalized
        self._apply_styles()
        # Capability/connection changes can temporarily detach this selector.
        # The message handler updates the page after all state is applied.

    def _apply_styles(self) -> None:
        for mode, button in self._mode_buttons.items():
            selected = mode == self._value
            button.bgcolor = "#1976D2" if selected else "#2B2F3A"
            button.border = ft.border.all(
                1,
                "#4FC3F7" if selected else "#3B3F4A",
            )
            content = button.content
            if isinstance(content, ft.Column):
                for control in content.controls:
                    if isinstance(control, ft.Icon):
                        control.color = "white" if selected else COLOR_DISABLED
                    elif isinstance(control, ft.Text):
                        control.color = "white" if selected else COLOR_TEXT_PRIMARY
