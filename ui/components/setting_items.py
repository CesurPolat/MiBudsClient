"""Setting items UI components."""

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_HOME_CONTROL,
    COLOR_HOME_BORDER,
    COLOR_HOME_SELECTED,
    COLOR_HOME_MUTED,
    COLOR_TEXT_PRIMARY,
    ICON_BUTTON_SIZE,
    ICON_BORDER_RADIUS,
)


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
                content=ft.Icon(icon, size=20, color=COLOR_TEXT_PRIMARY),
                bgcolor=COLOR_HOME_CONTROL,
                border=ft.Border.all(1, COLOR_HOME_BORDER),
                border_radius=ICON_BORDER_RADIUS,
                width=ICON_BUTTON_SIZE,
                height=ICON_BUTTON_SIZE,
                alignment=ft.Alignment.CENTER,
            ),
            title=ft.Text(title, size=14, color=COLOR_TEXT_PRIMARY, weight="w500"),
            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=COLOR_HOME_MUTED),
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
            active_color=COLOR_TEXT_PRIMARY,
            active_track_color=COLOR_HOME_SELECTED,
            inactive_track_color=COLOR_HOME_CONTROL,
        )

        super().__init__(
            leading=ft.Container(
                content=ft.Icon(icon, size=20, color=COLOR_TEXT_PRIMARY),
                bgcolor=COLOR_HOME_CONTROL,
                border=ft.Border.all(1, COLOR_HOME_BORDER),
                border_radius=ICON_BORDER_RADIUS,
                width=ICON_BUTTON_SIZE,
                height=ICON_BUTTON_SIZE,
                alignment=ft.Alignment.CENTER,
            ),
            title=ft.Text(title, size=14, color=COLOR_TEXT_PRIMARY, weight="w500"),
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
