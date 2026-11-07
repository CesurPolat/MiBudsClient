"""Home noise controls backed only by device-confirmed state."""
import math

import flet as ft

from controllers.bluetooth.noise import NoiseCapabilities
from utils.i18n import t, render
from ..constants import COLOR_DISABLED, COLOR_TEXT_PRIMARY, ICON_BORDER_RADIUS
from ..constants import HOME_CONTROL_HEADER_HEIGHT


class NoiseSettings:
    def __init__(self, on_action=None, on_update=lambda: None):
        self._on_action, self._on_update = on_action, on_update
        self.capabilities = NoiseCapabilities()
        self._connected = self._backend_enabled = self._busy = False
        self._token = 0
        self._session = self._state = self._error = None
        self._pending = {}
        self._operation = None
        self._preview = None
        self._last_anc_manual = None
        self.quick_status = ft.Text(size=12, color=COLOR_DISABLED, visible=False)
        self.retry_button = ft.TextButton(t("connection.retry"), visible=False,
                                         on_click=lambda _: self._act("read"))
        self.quick_mode_buttons = {}
        self._mode_icons, self._mode_progress = {}, {}
        for mode, icon in ((0, ft.Icons.DO_NOT_DISTURB), (1, ft.Icons.HEADPHONES), (2, ft.Icons.HEARING)):
            self._mode_icons[mode] = ft.Icon(icon, size=20)
            self._mode_progress[mode] = ft.ProgressRing(
                width=20, height=20, stroke_width=2, color="#9BC7FF", visible=False,
                semantics_label=t("noise.working"))
            self.quick_mode_buttons[mode] = ft.Button(
                content=ft.Column([
                    ft.Stack([self._mode_icons[mode], self._mode_progress[mode]], width=20, height=20),
                    ft.Text(t("noise.mode_" + str(mode)), size=11, weight="w500",
                            text_align=ft.TextAlign.CENTER),
                ], spacing=4, tight=True, alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                height=76, expand=True, disabled=True,
                on_click=lambda _, value=mode: self._choose_mode(value))
        self.quick_mode = ft.Row(list(self.quick_mode_buttons.values()), spacing=6, disabled=True)
        self.quick_level = ft.Slider(
            min=0, max=1, value=0, height=40, disabled=True,
            active_color="#1976D2", inactive_color="#343A46", thumb_color="#DCEBFF",
            overlay_color="#224FC3F7", year_2023=True,
            padding=ft.Padding.symmetric(horizontal=6),
            on_change=self._preview_quick_level,
            on_change_end=self._select_quick_level)
        self.quick_level_label = ft.Text(size=11, color=COLOR_DISABLED,
                                         text_align=ft.TextAlign.CENTER)
        self.special_level_buttons = {}
        self._special_progress = {}
        for value in (3, 4):
            self._special_progress[value] = ft.ProgressRing(width=14, height=14, stroke_width=2,
                                                            visible=False, color="#9BC7FF",
                                                            semantics_label=t("noise.working"))
            label_key = "noise.anc_adaptive" if value == 3 else "noise.anc_wind"
            self.special_level_buttons[value] = ft.Button(
                content=ft.Row([self._special_progress[value], ft.Text(t(label_key), size=11)],
                               spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                expand=True, height=36, visible=False,
                on_click=lambda _, level=value: self._select_special_level(level))
        self.special_level_controls = ft.Row(list(self.special_level_buttons.values()),
                                             spacing=6, visible=False)
        self._level_progress = ft.ProgressBar(height=2, color="#4FC3F7", bgcolor="transparent",
                                              opacity=0, semantics_label=t("noise.working"))
        self.quick_level_controls = ft.Container(
            content=ft.Column([self.quick_level, self._level_progress, self.quick_level_label],
                              spacing=0, tight=True,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            visible=False, padding=ft.Padding.only(top=4),
            theme=ft.Theme(slider_theme=ft.SliderTheme(
                track_height=4,
                active_tick_mark_color="#1976D2", inactive_tick_mark_color="#343A46",
                disabled_active_tick_mark_color="#1976D2", disabled_inactive_tick_mark_color="#343A46",
                disabled_active_track_color="#1976D2", disabled_inactive_track_color="#343A46",
                disabled_thumb_color="#9BC7FF")))
        self.quick_level_controls.dark_theme = self.quick_level_controls.theme
        self._header_icon = ft.Icon(ft.Icons.HEADPHONES, size=20, color=COLOR_TEXT_PRIMARY)
        self._read_progress = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False,
                                              color="#9BC7FF", semantics_label=t("noise.working"))
        self._quick_body = ft.Column([self.quick_mode], spacing=8, tight=True,
                                     horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.quick_controls = ft.Column([
            ft.ListTile(
                dense=True, min_height=44, height=HOME_CONTROL_HEADER_HEIGHT,
                content_padding=ft.Padding.symmetric(horizontal=8),
                leading=ft.Container(
                    content=ft.Stack([self._header_icon, self._read_progress], width=20, height=20),
                    bgcolor="blue_700", border_radius=ICON_BORDER_RADIUS, width=32, height=32,
                    alignment=ft.Alignment.CENTER),
                title=ft.Text(t("noise.title"), size=14, color=COLOR_TEXT_PRIMARY, weight="medium")),
            ft.Container(content=self._quick_body,
                padding=ft.Padding.only(left=8, right=8, bottom=6)),
        ], spacing=0, tight=True, visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def set_connection(self, connected, backend_enabled=False):
        if (self._connected, self._backend_enabled) == (connected, backend_enabled):
            self._render()
            return
        self._connected, self._backend_enabled = connected, backend_enabled
        self._token += 1
        self._state = self._session = self._error = None
        self._preview = self._last_anc_manual = None
        self._busy = False
        self._pending, self._operation = {}, None
        self._render()
        if connected and backend_enabled:
            self._act("read")

    def _act(self, operation, **kwargs):
        if self._connected and self._backend_enabled and not self._busy and self._on_action:
            if operation == "read" or self._state is not None:
                self._on_action(operation, **kwargs)

    def _choose_mode(self, mode):
        if mode in self.capabilities.modes and self._state and mode != self._state.mode:
            self._act("write", mode=mode)
        self._render()

    def _level_text(self, mode, value):
        levels = self.capabilities.levels(mode)
        if value not in levels:
            return t("noise.unknown", code=value)
        key = self.capabilities.level_label_key(mode, value)
        return t(key) if key else t("noise.level_value", value=levels.index(value) + 1)

    def _slider_selection(self, value):
        levels = self.capabilities.slider_levels(self._state.mode) if self._state else ()
        try:
            value = float(value)
            if not math.isfinite(value) or not 0 <= value <= len(levels) - 1:
                raise ValueError("Invalid level position")
            index = math.floor(value + .5)
            current = levels.index(self._state.level) if self._state.level in levels else None
            # Continuous rendering removes all marks. Keep keyboard increments
            # useful even when the native slider moves less than one gear.
            if current is not None and index == current and value != current:
                index += 1 if value > current else -1
        except (TypeError, ValueError, OverflowError):
            return None
        return value, levels[index]

    def _preview_quick_level(self, event):
        if self.quick_level.disabled:
            return
        selection = self._slider_selection(event.control.value)
        if selection is None:
            return
        position, level = selection
        self._preview = (self._state.mode, position, level)
        text = self._level_text(self._state.mode, level)
        self.quick_level_label.value = text
        # Flet publishes this event's control changes; no device write on drag.

    def _select_quick_level(self, event):
        selection = self._slider_selection(event.control.value)
        self._preview = None
        if selection is None or self.quick_level.disabled:
            self._render()
            return
        _, level = selection
        if level != self._state.level:
            self._act("write", mode=self._state.mode, level=level)
        self._render()

    def _select_special_level(self, level):
        if not self._state or self._state.mode != 1 or level not in self.capabilities.special_levels(1):
            return
        if level == self._state.level:
            regular = self.capabilities.slider_levels(1)
            if not regular:
                return
            level = self._last_anc_manual if self._last_anc_manual in regular else regular[0]
        self._act("write", mode=1, level=level)
        self._render()

    def begin(self, operation, session, **pending):
        if not self._connected or not self._backend_enabled or self._busy:
            return None
        self._token += 1
        self._preview = None
        self._session, self._busy = session, True
        self._operation, self._pending, self._error = operation, pending, None
        self._render()
        self._on_update()
        return self._token

    def complete(self, token, state, error=None):
        if token != self._token or not self._connected or not self._busy:
            return
        self._busy = False
        self._preview = None
        # A failed write rolls the thumb back to the last confirmed position.
        # Keep that position visible but locked until a fresh read succeeds.
        if not error or self._operation != "write":
            self._state = None if error else state
        self._pending, self._operation = {}, None
        self._error = error
        self._render()

    def notification(self, session, state):
        if self._connected and not self._busy and self._session == session:
            self._state, self._error = state, None
            self._render()

    def _render(self):
        enabled = self._connected and self._backend_enabled and not self._busy and self._state is not None and not self._error
        mode = self._state.mode if self._state else None
        level = self._state.level if self._state else None
        self.quick_mode.disabled = not enabled
        for value, button in self.quick_mode_buttons.items():
            selected = mode == value
            pending = self._busy and self._operation == "write" and "level" not in self._pending and self._pending.get("mode") == value
            button.visible = value in self.capabilities.modes
            button.disabled = not enabled
            self._mode_icons[value].visible = not pending
            self._mode_progress[value].visible = pending
            button.style = ft.ButtonStyle(
                bgcolor="#1976D2" if selected else "#2B2F3A", color=COLOR_TEXT_PRIMARY,
                side=ft.BorderSide(1, "#4FC3F7" if selected or pending else "#3B3F4A"),
                shape=ft.RoundedRectangleBorder(radius=ICON_BORDER_RADIUS), padding=8, elevation=0)
        all_levels = self.capabilities.levels(mode)
        levels = self.capabilities.slider_levels(mode)
        special_levels = self.capabilities.special_levels(mode)
        if mode == 1 and level in levels:
            self._last_anc_manual = level
        self.quick_level.max = max(1, len(levels) - 1)
        # Pending is a local thumb position, not a confirmed device setting.
        display_level = (self._pending.get("level", level)
                         if self._busy and self._operation == "write" and self._pending.get("mode") == mode
                         else level)
        preview = self._preview if self._preview and self._preview[0] == mode and not self._busy else None
        if preview:
            display_level = preview[2]
        self.quick_level.value = (preview[1] if preview else levels.index(display_level)
                                 if display_level in levels else 0)
        self.quick_level.disabled = not enabled or mode not in self.capabilities.modes or level not in levels or len(levels) < 2
        self.quick_level.visible = self.quick_level_controls.visible = True
        self.quick_level_controls.opacity = 1 if mode in (1, 2) and level in levels else .35
        text = (t("noise.mode_0") if mode == 0 else self._level_text(mode, display_level)
                if display_level is not None else t("noise.level"))
        self.quick_level_label.value = text
        for value, button in self.special_level_buttons.items():
            selected = level == value and value in special_levels
            pending = self._busy and self._pending.get("mode") == 1 and self._pending.get("level") == value
            button.visible = value in special_levels
            button.disabled = not enabled
            self._special_progress[value].visible = pending
            button.style = ft.ButtonStyle(
                bgcolor="#1976D2" if selected else "#2B2F3A", color=COLOR_TEXT_PRIMARY,
                side=ft.BorderSide(1, "#4FC3F7" if selected or pending else "#3B3F4A"),
                shape=ft.RoundedRectangleBorder(radius=ICON_BORDER_RADIUS), padding=8, elevation=0)
        self.special_level_controls.visible = bool(special_levels)
        self._level_progress.opacity = 1 if self._busy and "level" in self._pending else 0
        self._read_progress.visible = self._busy and self._operation == "read"
        self._header_icon.visible = not self._read_progress.visible
        self.quick_status.color = "red" if self._error else COLOR_DISABLED
        self.quick_status.value = ""
        if self._connected and not self._backend_enabled:
            self.quick_status.value = t("noise.unvalidated")
        elif self._error:
            self.quick_status.value = render(self._error)
        elif self._state and (mode not in self.capabilities.modes or (mode in (1, 2) and level not in all_levels)):
            self.quick_status.value = t("noise.unknown", code=mode if mode not in self.capabilities.modes else level)
        self.quick_status.visible = bool(self.quick_status.value)
        self.retry_button.visible = bool(self._error) and self._connected and self._backend_enabled
        self.retry_button.disabled = self._busy
        self._quick_body.controls = [self.quick_mode] + [
            control for control in (self.quick_level_controls, self.special_level_controls, self.quick_status, self.retry_button)
            if control.visible
        ]
