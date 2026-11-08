"""Latency UI components."""

from utils.i18n import t

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
    ICON_BORDER_RADIUS,
    HOME_CONTROL_HEADER_HEIGHT,
    COLOR_HOME_CONTROL,
    COLOR_HOME_BORDER,
    COLOR_HOME_SELECTED,
    COLOR_HOME_SELECTED_BORDER,
    COLOR_HOME_ACCENT,
    COLOR_HOME_MUTED,
    COLOR_HOME_SURFACE_TOP,
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
        self.on_activation_app_click = None
        self._activation_app = ""
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
            height=64,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=8,
        )

        self._device_state = ft.Text(t("latency.unknown"), size=12, color=COLOR_DISABLED,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        super().__init__(
            controls=[
                ft.ListTile(
                    dense=True, min_height=44, height=HOME_CONTROL_HEADER_HEIGHT,
                    content_padding=ft.Padding.symmetric(horizontal=8),
                    leading=ft.Container(
                        content=ft.Icon(icon, size=20, color=COLOR_TEXT_PRIMARY),
                        bgcolor=COLOR_HOME_CONTROL,
                        border_radius=ICON_BORDER_RADIUS,
                        width=32,
                        height=32,
                        alignment=ft.Alignment.CENTER,
                    ),
                    title=ft.Text(title, size=14, color=COLOR_TEXT_PRIMARY, weight="medium"),
                    subtitle=self._device_state,
                ),
                ft.Container(content=self._buttons_row, padding=ft.Padding.only(left=8, right=8, bottom=6)),
            ],
            spacing=0,
            tight=True,
        )
        self._apply_styles()

    @property
    def value(self) -> str:
        return self._value

    def set_device_state(self, enabled: Optional[bool], activation_app: str = "") -> None:
        self._activation_app = activation_app if self._value == "auto" and enabled is True else ""
        self._device_state.spans = []
        self._device_state.tooltip = self._activation_app or None
        if self._activation_app:
            self._device_state.value = ""
            self._device_state.spans = [
                ft.TextSpan(self._activation_app,
                            style=ft.TextStyle(color="#9BC7FF"),
                            on_click=self._open_activation_app),
                ft.TextSpan(t("latency.auto_activated")),
            ]
            return
        self._device_state.value = t("latency.unknown") if enabled is None else t(
            "latency.enabled" if enabled else "latency.standard_set")

    def _open_activation_app(self, _) -> None:
        if self._activation_app and self.on_activation_app_click:
            self.on_activation_app_click(self._activation_app)

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
            button.bgcolor = COLOR_HOME_SELECTED if selected else COLOR_HOME_CONTROL
            button.gradient = ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=([COLOR_HOME_SELECTED_BORDER, COLOR_HOME_SELECTED] if selected
                        else [COLOR_HOME_CONTROL, COLOR_HOME_SURFACE_TOP]))
            button.shadow = (ft.BoxShadow(
                blur_radius=12, spread_radius=0, color="#402463FF",
                offset=ft.Offset(0, 3)) if selected else None)
            button.border = ft.border.all(
                1,
                COLOR_HOME_SELECTED_BORDER if selected else COLOR_HOME_BORDER,
            )
            content = button.content
            if isinstance(content, ft.Column):
                for control in content.controls:
                    if isinstance(control, ft.Icon):
                        control.color = COLOR_HOME_ACCENT if selected else COLOR_HOME_MUTED
                    elif isinstance(control, ft.Text):
                        control.color = "white" if selected else COLOR_TEXT_PRIMARY
