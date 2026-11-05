"""Function-list noise controls; display device-confirmed state only."""
import flet as ft
from controllers.bluetooth.noise import NoiseCapabilities
from utils.i18n import t, render
from .setting_items import SettingItem
from ..constants import COLOR_DISABLED, COLOR_TEXT_PRIMARY, ICON_BORDER_RADIUS


class NoiseSettings(ft.Column):
    def __init__(self, on_action=None, on_update=lambda: None):
        self._on_action, self._on_update = on_action, on_update
        self.capabilities = NoiseCapabilities()
        self._connected = self._opened = self._busy = False
        self._backend_enabled = False
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
        self.quick_status = ft.Text(t("noise.open"), color=COLOR_DISABLED, size=12)
        self.quick_mode_buttons = {}
        for mode, icon in ((0, ft.Icons.DO_NOT_DISTURB), (1, ft.Icons.HEADPHONES), (2, ft.Icons.HEARING)):
            self.quick_mode_buttons[mode] = ft.Button(
                content=ft.Column([
                    ft.Icon(icon, size=20),
                    ft.Text(t("noise.mode_" + str(mode)), size=11, weight="w500",
                            text_align=ft.TextAlign.CENTER),
                ], spacing=4, tight=True, alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                height=76, expand=True, disabled=True,
                tooltip=t("noise.mode_" + str(mode)),
                on_click=lambda _, value=mode: self._choose_mode(value))
        self.quick_mode = ft.Row(list(self.quick_mode_buttons.values()), spacing=6, disabled=True)
        self.quick_level = ft.Slider(min=0, max=1, value=0, divisions=1, disabled=True,
                                     active_color="#1976D2", tooltip=t("noise.level"),
                                     on_change_end=self._select_quick_level)
        self.quick_level_label = ft.Text(t("noise.level"), size=12, color=COLOR_TEXT_PRIMARY)
        self.quick_level_controls = ft.Column([self.quick_level_label, self.quick_level], spacing=0,
                                               visible=False,
                                               horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.quick_refresh = ft.IconButton(icon=ft.Icons.REFRESH, tooltip=t("noise.refresh"),
                                           disabled=True, on_click=lambda _: self._act("read"))
        self.quick_controls = ft.Column([
            ft.ListTile(
                dense=True, min_height=44,
                content_padding=ft.Padding.symmetric(horizontal=8),
                leading=ft.Container(
                    content=ft.Icon(ft.Icons.HEADPHONES, size=20, color=COLOR_TEXT_PRIMARY),
                    bgcolor="blue_700", border_radius=ICON_BORDER_RADIUS, width=32, height=32),
                title=ft.Text(t("noise.title"), size=14, color=COLOR_TEXT_PRIMARY, weight="medium"),
                trailing=self.quick_refresh),
            ft.Container(content=ft.Column([
                self.quick_mode, self.quick_level_controls, self.quick_status,
            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=ft.Padding.only(left=8, right=8, bottom=6)),
        ], spacing=0, visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        super().__init__([self.toggle, self.body], spacing=8)

    def set_connection(self, connected, backend_enabled=False):
        if (self._connected, self._backend_enabled) == (connected, backend_enabled):
            self._render()
            return
        self._connected = connected
        self._backend_enabled = backend_enabled
        self._token += 1
        self._state = self._session = None
        self._busy = False
        self.status.value = t("noise.open")
        self.status.color = COLOR_DISABLED
        self._render()
        if connected and backend_enabled:
            self._act("read")

    def _toggle(self, _):
        self._opened = not self._opened
        self.body.visible = self._opened
        self._on_update()

    def _act(self, operation, **kwargs):
        if self._connected and self._backend_enabled and not self._busy and self._on_action:
            if operation == "read" or self._state is not None:
                self._on_action(operation, **kwargs)

    def _select_mode(self, event):
        try:
            mode = int(event.control.value)
        except (TypeError, ValueError):
            return
        self._choose_mode(mode)

    def _choose_mode(self, mode):
        if mode in self.capabilities.modes and self._state and mode != self._state.mode:
            self._act("write", mode=mode)
        self._render()  # Never display an unconfirmed requested state.

    def _select_quick_level(self, event):
        # Slider positions follow catalog order, not raw protocol byte values.
        levels = self.capabilities.levels(self._state.mode) if self._state else ()
        try:
            value = float(event.control.value)
            index = round(value)
            if value != index or not 0 <= index < len(levels):
                raise ValueError("Invalid level position")
        except (TypeError, ValueError, OverflowError):
            self._render()
            return
        if levels[index] != self._state.level:
            self._act("write", mode=self._state.mode, level=levels[index])
        self._render()

    def _select_level(self, event):
        try:
            level = int(event.control.value)
        except (TypeError, ValueError):
            return
        if self._state and level in self.capabilities.levels(self._state.mode) and level != self._state.level:
            self._act("write", mode=self._state.mode, level=level)
        self._render()

    def begin(self, operation, session):
        if not self._connected or not self._backend_enabled or self._busy:
            return None
        self._token += 1
        self._session, self._busy = session, True
        self.status.value = t("noise.working")
        self.status.color = COLOR_DISABLED
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
        enabled = self._connected and self._backend_enabled and not self._busy and self._state is not None
        self.refresh.disabled = not self._connected or not self._backend_enabled or self._busy
        if self._connected and not self._backend_enabled:
            self.status.value = t("noise.unvalidated")
            self.status.color = COLOR_DISABLED
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
        self.level.visible = mode in (1, 2) and bool(levels)
        self.level.disabled = not enabled or not levels or mode not in self.capabilities.modes
        self.quick_mode.disabled = not enabled
        for value, button in self.quick_mode_buttons.items():
            selected = mode == value
            button.visible = value in self.capabilities.modes
            button.disabled = not enabled
            button.style = ft.ButtonStyle(
                bgcolor="#1976D2" if selected else "#2B2F3A", color=COLOR_TEXT_PRIMARY,
                side=ft.BorderSide(1, "#4FC3F7" if selected else "#3B3F4A"),
                shape=ft.RoundedRectangleBorder(radius=ICON_BORDER_RADIUS),
                padding=8, elevation=0)
        self.quick_level.max = max(1, len(levels) - 1)
        self.quick_level.divisions = max(1, len(levels) - 1)
        self.quick_level.value = levels.index(level) if level in levels else 0
        self.quick_level.disabled = self.level.disabled or level not in levels or len(levels) < 2
        self.quick_level.visible = self.level.visible
        self.quick_level_controls.visible = self.level.visible
        self.quick_level_label.value = (t("noise.level_value", value=level) if level in levels
                                        else t("noise.unknown", code=level))
        self.quick_refresh.disabled = self.refresh.disabled
        self.quick_status.value, self.quick_status.color = self.status.value, self.status.color
        unknown_mode = self._state is not None and mode not in self.capabilities.modes
        if unknown_mode:
            self.quick_status.value = t("noise.unknown", code=mode)
        self.quick_status.visible = self._state is None or self._busy or unknown_mode
