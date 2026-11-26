"""General settings for startup and language."""

import flet as ft

from utils.app.i18n import LANGUAGES, t
from utils.app.user_preferences import get_language_preference

from ...constants import COLOR_DIVIDER, COLOR_HOME_CONTROL
from ..shared.common import settings_input_border
from ..shared.setting_items import ToggleSettingItem


class GeneralSection(ft.Container):
    def __init__(self, startup_enabled, on_startup_toggle, on_language_change):
        self.startup_item = ToggleSettingItem(
            ft.Icons.ROCKET_LAUNCH, "deep_orange_700", t("startup.title"),
            value=startup_enabled,
            on_change=on_startup_toggle,
        )
        self.language_selector = ft.Dropdown(
            label=t("language.title"),
            value=get_language_preference(),
            options=[ft.DropdownOption("system", t("language.system"))] + [
                ft.DropdownOption(code, name) for code, name in LANGUAGES.items()
            ],
            on_select=on_language_change,
            color="white",
            filled=True,
            fill_color=COLOR_HOME_CONTROL,
            border=settings_input_border(12),
            expand=True,
        )
        super().__init__(
            content=ft.Column(
                [
                    self.startup_item,
                    ft.Divider(height=1, color=COLOR_DIVIDER),
                    ft.Container(content=self.language_selector, padding=10),
                ],
                spacing=6,
            ),
            padding=0,
        )
