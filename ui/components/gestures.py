"""Flet gesture editor; only device-confirmed assignments are displayed."""

import flet as ft

from controllers.bluetooth.gestures import ACTION_NAMES, GESTURE_NAMES
from ..constants import COLOR_TEXT_PRIMARY, COLOR_DISABLED
from .setting_items import SettingItem


class GestureSettings(ft.Column):
    def __init__(self, on_refresh=None, on_assignment=None, on_update=lambda: None):
        self._on_refresh = on_refresh
        self._on_assignment = on_assignment
        self._on_update = on_update
        self._connected = False
        self._opened = False
        self._token = 0
        self._busy = False
        self._needs_refresh = True
        self._assignments = {}
        self._capabilities = {}
        self.selectors = {}
        self.status = ft.Text("Connect your earbuds to manage gestures.", size=12, color=COLOR_DISABLED)
        self.refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH, tooltip="Refresh gestures", disabled=True, visible=False,
            on_click=lambda _: self._refresh(),
        )
        self.toggle_button = SettingItem(ft.Icons.TOUCH_APP, "blue_700", "Gestures", on_click=self._toggle)
        self.rows = ft.Column(spacing=12)
        self.body = ft.Column([self.status, self.refresh_button, self.rows], visible=False)
        super().__init__([
            ft.Container(content=ft.Text("Earbud Management", weight="w600", color=COLOR_TEXT_PRIMARY), padding=10),
            self.toggle_button, self.body,
        ], spacing=8)

    def _toggle(self, _):
        self._opened = not self._opened
        self.body.visible = self._opened
        self.toggle_button.trailing.icon = ft.Icons.EXPAND_LESS if self._opened else ft.Icons.CHEVRON_RIGHT
        if self._opened:
            self._refresh()
        self._on_update()

    def _refresh(self):
        if self._connected and not self._busy and self._on_refresh:
            self._on_refresh()

    def set_connection(self, connected):
        if connected == self._connected:
            return
        self._connected = connected
        self._token += 1
        self._busy = False
        self._needs_refresh = True
        self._assignments = {}
        self._capabilities = {}
        self.status.value = "Open gestures to read assignments." if connected else "Connect your earbuds to manage gestures."
        self.status.color = COLOR_DISABLED
        self._render()
        if connected and self._opened:
            self._refresh()

    def begin(self, message):
        if not self._connected or self._busy:
            return None
        self._token += 1
        token = self._token
        self._busy = True
        self.status.value = message
        self.status.color = COLOR_DISABLED
        self._render()
        self._on_update()
        return token

    def complete(self, token, result, capabilities):
        if token != self._token or not self._connected or not self._busy:
            return
        self._busy = False
        self._needs_refresh = not result.success
        if result.success:
            self._assignments = dict(result.assignments)
            self._capabilities = dict(capabilities)
        self.status.value = result.message
        self.status.color = "green" if result.success else "red"
        if result.success and not (self._assignments.keys() & self._capabilities.keys()):
            self.status.value = "The earbuds returned no supported gesture assignments."
        self._render()

    def _change(self, gesture, side, event):
        if self._busy or not self._connected or self._needs_refresh:
            return
        value = event.control.value
        if value is None:
            return
        try:
            action = int(value)
        except (ValueError, TypeError):
            return
        if action not in self._capabilities.get(gesture, ()):
            return
        current = self._assignments[gesture][0 if side == "left" else 1]
        if action != current and self._on_assignment:
            self._on_assignment(gesture, side, action)

    def _render(self):
        self.refresh_button.disabled = not self._connected or self._busy
        self.selectors = {}
        self.rows.controls = []
        for gesture, title in GESTURE_NAMES.items():
            if gesture not in self._assignments or gesture not in self._capabilities:
                continue
            fields = []
            for index, side in enumerate(("left", "right")):
                current = self._assignments[gesture][index]
                allowed = self._capabilities[gesture]
                options = [ft.dropdown.Option(str(action), ACTION_NAMES[action]) for action in allowed]
                if current not in allowed:
                    label = ACTION_NAMES.get(current, f"Unknown (0x{current:02X})")
                    options.append(ft.dropdown.Option(str(current), f"Current: {label}", disabled=True))
                selector = ft.Dropdown(
                    label=side.title(), value=str(current), options=options,
                    disabled=self._busy or not self._connected or self._needs_refresh, expand=True,
                    color=COLOR_TEXT_PRIMARY, bgcolor="#151922", filled=True,
                    fill_color="#151922", border_color="#2A303C",
                    label_style=ft.TextStyle(color=COLOR_DISABLED), text_size=13,
                    on_select=lambda e, g=gesture, s=side: self._change(g, s, e),
                )
                self.selectors[(gesture, side)] = selector
                fields.append(selector)
            self.rows.controls.extend([ft.Text(title, size=13, color=COLOR_TEXT_PRIMARY), ft.Row(fields, spacing=8)])
