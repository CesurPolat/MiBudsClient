"""Flet EQ controls with separate local draft and device-confirmed state."""
import flet as ft

from controllers.bluetooth.equalizer import EqBand, PROFILE_KEYS
from utils.i18n import t, render
from .setting_items import SettingItem
from ..constants import COLOR_DISABLED, COLOR_TEXT_PRIMARY, ICON_BORDER_RADIUS
from ..constants import HOME_CONTROL_HEADER_HEIGHT
from ..constants import (
    COLOR_HOME_CONTROL, COLOR_HOME_BORDER, COLOR_HOME_SELECTED,
    COLOR_HOME_SELECTED_BORDER,
)


class EqualizerSettings(ft.Column):
    def __init__(self, on_action=None, on_update=lambda: None):
        self._on_action = on_action
        self._on_update = on_update
        self.custom_supported = False
        self._connected = False
        self._opened = False
        self._busy = False
        self._needs_refresh = True
        self._token = 0
        self._state = None
        self._profiles = ()
        self.draft = ()
        self.status = ft.Text(t("eq.connect"), size=12, color=COLOR_DISABLED)
        self.refresh_button = ft.IconButton(icon=ft.Icons.REFRESH, tooltip=t("eq.refresh"),
                                          disabled=True, on_click=lambda _: self._act("read"))
        self.profile = ft.Dropdown(label=t("eq.profile"), disabled=True, options=[],
                                   on_select=self._select, color=COLOR_TEXT_PRIMARY, filled=True)
        self.quick_status = ft.Text(t("eq.connect"), size=12, color=COLOR_DISABLED, visible=False)
        self.quick_profiles = ft.Row(height=64, spacing=4)
        self._feedback_active = False
        self._feedback_started = False
        self._feedback_profile = None
        self._button_feedback = {}
        self.quick_refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH, tooltip=t("eq.refresh"), disabled=True, visible=False,
            on_click=lambda _: self._act("read"))
        self.quick_controls = ft.Column([
            ft.ListTile(
                dense=True, min_height=44, height=HOME_CONTROL_HEADER_HEIGHT,
                content_padding=ft.Padding.symmetric(horizontal=8),
                leading=ft.Container(
                    content=ft.Icon(ft.Icons.GRAPHIC_EQ, size=20, color=COLOR_TEXT_PRIMARY),
                    bgcolor=COLOR_HOME_CONTROL, border_radius=ICON_BORDER_RADIUS,
                    width=32, height=32, alignment=ft.Alignment.CENTER),
                title=ft.Text(t("eq.title"), size=14, color=COLOR_TEXT_PRIMARY, weight="medium"),
                trailing=self.quick_refresh_button),
            ft.Container(
                content=ft.Column([self.quick_profiles, self.quick_status], spacing=4,
                                  horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=ft.Padding.only(left=8, right=8, bottom=6)),
        ], spacing=0, tight=True, visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.sliders = []
        self.rows = ft.Column(spacing=4)
        self.save_button = ft.TextButton(t("eq.save"), disabled=True, on_click=lambda _: self._act("save"))
        self.reset_button = ft.TextButton(t("eq.reset"), disabled=True, on_click=lambda _: self._act("reset"))
        self.custom_body = ft.Column([
            ft.Text(t("eq.custom"), color=COLOR_TEXT_PRIMARY), self.rows,
            ft.Row([self.save_button, self.reset_button]),
        ], visible=False)
        self.body = ft.Column([self.status, self.refresh_button, self.profile, self.custom_body], visible=False)
        self.toggle = SettingItem(ft.Icons.GRAPHIC_EQ, "blue_700", t("eq.title"), on_click=self._toggle)
        super().__init__([self.toggle, self.body], spacing=8)

    def _toggle(self, _):
        self._opened = not self._opened
        self.body.visible = self._opened
        self.toggle.trailing.icon = ft.Icons.EXPAND_LESS if self._opened else ft.Icons.CHEVRON_RIGHT
        if self._opened and self._needs_refresh:
            self._act("read")
        self._on_update()

    @property
    def ready(self):
        return self._connected and self._state is not None and bool(self._profiles)

    @property
    def initial_read_failed(self):
        return self._connected and not self.ready and not self._busy and self.status.color == "red"

    def retry_initial_read(self):
        self._act("read")

    def set_connection(self, connected):
        if self._connected == connected:
            return
        self._connected = connected
        self._token += 1
        self._busy = False
        self._needs_refresh = True
        self._state = None
        self._profiles = ()
        self.draft = ()
        self.status.value = t("eq.open" if connected else "eq.connect")
        self.status.color = COLOR_DISABLED
        self.quick_controls.visible = connected
        self._render()
        if connected:
            self._act("read")

    def _set_feedback(self, active):
        if active and not self._feedback_started:
            self._feedback_started = True
            self._feedback_active = True
        elif not self._connected or self._needs_refresh:
            self._feedback_active = False
        self._paint_feedback()

    def _paint_feedback(self):
        for profile, feedback in self._button_feedback.items():
            selected = self._feedback_active and profile == self._feedback_profile
            feedback.border = ft.Border.all(1, "#664FC3F7" if selected else "transparent")

    def _pulse_feedback(self, _, profile):
        if profile != self._feedback_profile or not self._feedback_active:
            return
        self._feedback_active = False
        self._paint_feedback()
        self._on_update()

    def _act(self, operation, **kwargs):
        if operation not in ("read", "profile") and not self.custom_supported:
            return
        if not self._connected or self._busy or (operation != "read" and self._needs_refresh):
            return
        if self._on_action:
            self._feedback_profile = kwargs.get("profile") if operation == "profile" else None
            self._paint_feedback()
            self._on_action(operation, bands=tuple(self.draft), **kwargs)

    def _select(self, event):
        try:
            profile = int(event.control.value)
        except (TypeError, ValueError):
            return
        self._select_profile(profile)

    def _select_profile(self, profile):
        if profile in self._profiles and self._state and profile != self._state.profile:
            self._act("profile", profile=profile)

    def _change(self, index, event):
        if self._busy or not self._connected or self._needs_refresh:
            return
        band = self.draft[index]
        gain = round(float(event.control.value))
        if not -self._state.custom.bound <= gain <= self._state.custom.bound:
            return
        draft = list(self.draft)
        draft[index] = EqBand(band.frequency, gain)
        self.draft = tuple(draft)
        self.rows.controls[index].controls[0].value = self._band_label(self.draft[index])
        self._on_update()

    @staticmethod
    def _band_label(band):
        return f"{band.frequency} Hz   {band.gain:+d} dB"

    def begin(self, operation):
        if not self._connected or self._busy:
            return None
        self._token += 1
        self._busy = True
        self._feedback_started = False
        self.status.value = t("eq.reading" if operation == "read" else "eq.working")
        self._render()
        self._on_update()
        return self._token

    def complete(self, token, result, profiles, operation):
        if token != self._token or not self._connected or not self._busy:
            return
        self._busy = False
        self._needs_refresh = not result.success
        if result.success:
            self._state = result.state
            self._profiles = tuple(p for p in profiles if p in PROFILE_KEYS and p != 10)
            if operation != "preview":
                self.draft = result.state.custom.bands if result.state.custom else ()
        self.status.value = render(result.message)
        self.status.color = "green" if result.success else "red"
        self._render()

    def _render(self):
        enabled = self._connected and not self._busy and not self._needs_refresh
        self.refresh_button.disabled = not self._connected or self._busy
        current = self._state.profile if self._state else None
        self.profile.options = [ft.dropdown.Option(str(p), t("eq." + PROFILE_KEYS[p])) for p in self._profiles]
        if current is not None and current != 10 and current not in self._profiles:
            self.profile.options.append(ft.dropdown.Option(str(current), t("eq.current", code=f"{current:02X}"), disabled=True))
        self.profile.value = str(current) if current is not None and current != 10 else None
        self.profile.disabled = not enabled or current is None or not self._profiles
        icons = {
            0: ft.Icons.TUNE, 1: ft.Icons.MIC, 2: ft.Icons.ELECTRIC_BOLT,
            3: ft.Icons.PIANO, 4: ft.Icons.MUSIC_NOTE, 5: ft.Icons.SPEAKER,
            6: ft.Icons.GRAPHIC_EQ, 7: ft.Icons.VOLUME_UP, 11: ft.Icons.PIANO,
            12: ft.Icons.HEADPHONES, 13: ft.Icons.VOLUME_DOWN,
            14: ft.Icons.WAVES, 15: ft.Icons.WORKSPACE_PREMIUM,
            16: ft.Icons.SETTINGS_INPUT_COMPONENT, 17: ft.Icons.PARK,
            18: ft.Icons.WATER, 21: ft.Icons.BALANCE,
        }
        buttons = [
            ft.TextButton(
                content=ft.Column([
                    ft.Icon(icons.get(int(option.key), ft.Icons.GRAPHIC_EQ),
                            size=16, color=COLOR_TEXT_PRIMARY),
                    ft.Text(option.text, size=10, color=COLOR_TEXT_PRIMARY,
                            style=ft.TextStyle(height=1.0),
                            text_align=ft.TextAlign.CENTER, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=2, alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                height=60,
                data=int(option.key),
                disabled=self.profile.disabled or option.disabled,
                style=ft.ButtonStyle(
                    bgcolor=COLOR_HOME_SELECTED if option.key == self.profile.value else COLOR_HOME_CONTROL,
                    side=ft.BorderSide(1, COLOR_HOME_SELECTED_BORDER if option.key == self.profile.value else COLOR_HOME_BORDER),
                    color=COLOR_TEXT_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding.symmetric(horizontal=2, vertical=2)),
                on_click=lambda e: self._select_profile(e.control.data))
            for option in self.profile.options]
        wrappers = {}
        for button in buttons:
            profile = button.data
            feedback = self._button_feedback.get(profile)
            if feedback is None:
                feedback = ft.Container(
                    expand=True, height=64, padding=2, border_radius=14,
                    border=ft.Border.all(1, "transparent"),
                    animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
                    on_animation_end=lambda e, p=profile: self._pulse_feedback(e, p))
            feedback.content = button
            wrappers[profile] = feedback
        self._button_feedback = wrappers
        self.quick_profiles.controls = list(wrappers.values())
        self.quick_refresh_button.disabled = self.refresh_button.disabled
        self.quick_status.value = self.status.value
        self.quick_status.color = self.status.color
        self.quick_status.visible = self._connected and not self._busy and self.status.color == "red"
        self._set_feedback(self._connected and self._busy and self._feedback_profile in wrappers)
        self._paint_feedback()
        self.custom_body.visible = bool(self.custom_supported and self._state and self._state.custom)
        self.save_button.disabled = self.reset_button.disabled = not (enabled and self.custom_body.visible)
        self.sliders = []
        self.rows.controls = []
        if self._state and self._state.custom:
            bound = self._state.custom.bound
            for index, band in enumerate(self.draft):
                slider = ft.Slider(min=-bound, max=bound, divisions=2 * bound, value=band.gain,
                                   label="{value} dB", disabled=not enabled,
                                   on_change=lambda e, i=index: self._change(i, e),
                                   on_change_end=lambda _: self._act("preview"))
                self.sliders.append(slider)
                self.rows.controls.append(ft.Column([
                    ft.Text(self._band_label(band), size=12, color=COLOR_TEXT_PRIMARY), slider,
                ], spacing=0))
