"""Flet EQ controls with separate local draft and device-confirmed state."""
import flet as ft

from controllers.bluetooth.equalizer import EqBand, PROFILE_KEYS
from utils.i18n import t, render
from .setting_items import SettingItem
from ..constants import COLOR_DISABLED, COLOR_TEXT_PRIMARY


class EqualizerSettings(ft.Column):
    def __init__(self, on_action=None, on_update=lambda: None):
        self._on_action = on_action
        self._on_update = on_update
        self.custom_supported = True
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
                                          disabled=True, visible=False, on_click=lambda _: self._act("read"))
        self.profile = ft.Dropdown(label=t("eq.profile"), disabled=True, options=[],
                                   on_select=self._select, color=COLOR_TEXT_PRIMARY, filled=True)
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
        if self._opened:
            self._act("read")
        self._on_update()

    def set_connection(self, connected):
        if self._connected == connected:
            return
        self._connected = connected
        self._token += 1
        self._busy = False
        self._needs_refresh = True
        self._state = None
        self.draft = ()
        self.status.value = t("eq.open" if connected else "eq.connect")
        self._render()
        if connected and self._opened:
            self._act("read")

    def _act(self, operation, **kwargs):
        if operation not in ("read", "profile") and not self.custom_supported:
            return
        if not self._connected or self._busy or (operation != "read" and self._needs_refresh):
            return
        if self._on_action:
            self._on_action(operation, bands=tuple(self.draft), **kwargs)

    def _select(self, event):
        try:
            profile = int(event.control.value)
        except (TypeError, ValueError):
            return
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
            self._profiles = tuple(profiles)
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
        if current is not None and current not in self._profiles:
            self.profile.options.append(ft.dropdown.Option(str(current), t("eq.current", code=f"{current:02X}"), disabled=True))
        self.profile.value = str(current) if current is not None else None
        self.profile.disabled = not enabled or current is None or not self._profiles
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
