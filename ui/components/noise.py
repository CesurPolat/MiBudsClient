"""Function-list noise controls; display device-confirmed state only."""
import flet as ft
from controllers.bluetooth.noise import NoiseCapabilities
from utils.i18n import t, render
from .setting_items import SettingItem
from ..constants import COLOR_DISABLED, COLOR_TEXT_PRIMARY


class NoiseSettings(ft.Column):
    def __init__(self, on_action=None, on_update=lambda: None):
        self._on_action, self._on_update = on_action, on_update
        self.capabilities = NoiseCapabilities()
        self._connected = self._opened = self._busy = False
        self._token = 0
        self._session = None
        self._state = None
        self.status = ft.Text(t("noise.open"), color=COLOR_DISABLED, size=12)
        self.mode = ft.Dropdown(label=t("noise.mode"), options=[], disabled=True,
                                on_select=self._select_mode, color=COLOR_TEXT_PRIMARY)
        self.level = ft.Dropdown(label=t("noise.level"), options=[], disabled=True,
                                 on_select=self._select_level, color=COLOR_TEXT_PRIMARY)
        self.refresh = ft.TextButton(t("noise.refresh"), on_click=lambda _: self._act("read"))
        self.body = ft.Column([self.status,
                               self.refresh, self.mode, self.level], visible=False)
        self.toggle = SettingItem(ft.Icons.HEADPHONES, "blue_700", t("noise.title"), on_click=self._toggle)
        super().__init__([self.toggle, self.body], spacing=8)

    def set_connection(self, connected):
        if self._connected == connected:
            return
        self._connected = connected
        self._token += 1
        self._state = self._session = None
        self._busy = False
        self.status.value = t("noise.open")
        self._render()
        if connected and self._opened:
            self._act("read")

    def _toggle(self, _):
        self._opened = not self._opened
        self.body.visible = self._opened
        if self._opened:
            self._act("read")
        self._on_update()

    def _act(self, operation, **kwargs):
        if self._connected and not self._busy and self._on_action:
            if operation == "read" or self._state is not None:
                self._on_action(operation, **kwargs)

    def _select_mode(self, event):
        try:
            mode = int(event.control.value)
        except (TypeError, ValueError):
            return
        if mode in self.capabilities.modes and self._state and mode != self._state.mode:
            self._act("write", mode=mode)
        self._render()  # Never display an unconfirmed requested state.

    def _select_level(self, event):
        try:
            level = int(event.control.value)
        except (TypeError, ValueError):
            return
        if self._state and level in self.capabilities.levels(self._state.mode) and level != self._state.level:
            self._act("write", mode=self._state.mode, level=level)
        self._render()

    def begin(self, operation, session):
        if not self._connected or self._busy:
            return None
        self._token += 1
        self._session, self._busy = session, True
        self.status.value = t("noise.working")
        self._render()
        self._on_update()
        return self._token

    def complete(self, token, state, error=None):
        if token != self._token or not self._connected or not self._busy:
            return
        self._busy = False
        self._state = None if error else state
        self.status.value = render(error) if error else t("noise.loaded")
        self.status.color = "red" if error else COLOR_DISABLED
        self._render()

    def notification(self, session, state):
        if self._connected and not self._busy and self._session == session:
            self._state = state
            self._render()

    def _render(self):
        enabled = self._connected and not self._busy and self._state is not None
        self.refresh.disabled = not self._connected or self._busy
        self.mode.options = [ft.dropdown.Option(str(v), t("noise.mode_" + str(v)))
                             for v in self.capabilities.modes]
        mode = self._state.mode if self._state else None
        if mode is not None and mode not in self.capabilities.modes:
            self.mode.options.append(ft.dropdown.Option(str(mode), t("noise.unknown", code=mode), disabled=True))
        self.mode.value = str(mode) if mode is not None else None
        self.mode.disabled = not enabled
        levels = self.capabilities.levels(mode)
        self.level.options = [ft.dropdown.Option(str(v), t("noise.level_value", value=v)) for v in levels]
        level = self._state.level if self._state else None
        if mode in (1, 2) and level is not None and level not in levels:
            self.level.options.append(ft.dropdown.Option(str(level), t("noise.unknown", code=level), disabled=True))
        self.level.value = str(level) if mode in (1, 2) and level is not None else None
        self.level.visible = mode in (1, 2)
        self.level.disabled = not enabled or not levels or mode not in self.capabilities.modes
