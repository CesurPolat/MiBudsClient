"""Setting items UI components."""

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_BATTERY,
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
