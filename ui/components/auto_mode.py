"""Auto mode UI components."""

import flet as ft
from typing import Callable, Optional

from ..constants import (
    COLOR_DISABLED,
    COLOR_TEXT_PRIMARY,
)

from .setting_items import ToggleSettingItem


class PlatformExceptionEditor(ft.Column):
    """Editor for a single platform list."""

    def __init__(
        self,
        platform_key: str,
        label: str,
        placeholder: str,
        values: list[str],
        on_add: Optional[Callable[[str, str], None]] = None,
        on_remove: Optional[Callable[[str, str], None]] = None,
    ):
        self._platform_key = platform_key
        self._on_add = on_add
        self._on_remove = on_remove
        self._values = sorted({(value or "").strip().lower() for value in values if value and value.strip()})

        self._list_column = ft.Column(spacing=4)
        self._field = ft.TextField(
            hint_text=placeholder,
            dense=True,
            expand=True,
            on_submit=self._add_value,
        )

        self._editor_surface = ft.Container(
            content=ft.Row(
                controls=[
                    self._field,
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip="Add",
                        on_click=self._add_value,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#151922",
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, "#2A303C"),
        )

        self._render_rows()
        content_column = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Text(label, size=12, color=COLOR_TEXT_PRIMARY, weight="w600"),
                    padding=ft.padding.only(left=4, bottom=2),
                ),
                self._editor_surface,
                self._list_column,
            ],
            spacing=8,
        )
        super().__init__(
            controls=[
                ft.Container(
                    content=content_column,
                    padding=ft.padding.symmetric(horizontal=6, vertical=4),
                )
            ],
            spacing=0,
        )

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _add_value(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        if value in self._values:
            self._field.value = ""
            self._field.update()
            return

        self._values.append(value)
        self._values.sort()
        if self._on_add:
            self._on_add(self._platform_key, value)
        self._field.value = ""
        self._render_rows()
        self.update()

    def _remove_value(self, value: str):
        if value not in self._values:
            return
        self._values.remove(value)
        if self._on_remove:
            self._on_remove(self._platform_key, value)
        self._render_rows()
        self.update()

    def _render_rows(self):
        if not self._values:
            self._list_column.controls = [
                ft.Container(
                    content=ft.Text("No entries.", size=12, color=COLOR_DISABLED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    bgcolor="#12161E",
                    border_radius=12,
                    border=ft.border.all(1, "#2A303C"),
                )
            ]
            return

        self._list_column.controls = [
            ft.Container(
                content=ft.ListTile(
                    dense=True,
                    title=ft.Text(item, size=13, color=COLOR_TEXT_PRIMARY),
                    trailing=ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Remove",
                        icon_color=COLOR_DISABLED,
                        on_click=lambda e, name=item: self._remove_value(name),
                    ),
                ),
                bgcolor="#12161E",
                border_radius=12,
                padding=ft.padding.only(left=6, right=4),
                border=ft.border.all(1, "#2A303C"),
            )
            for item in self._values
        ]

    def set_values(self, values: list[str]) -> None:
        self._values = sorted({(value or "").strip().lower() for value in values if value and value.strip()})
        self._render_rows()
        self.update()


class AutoModeSettingsAccordion(ft.ExpansionTile):
    """Accordion for automatic mode per-app rule settings."""

    def __init__(
        self,
        exclusions_by_platform: dict[str, list[str]],
        inclusions_by_platform: dict[str, list[str]],
        active_platform: str,
        wait_until_app_close_enabled: bool = False,
        on_wait_until_app_close_change: Optional[Callable] = None,
        on_add_item: Optional[Callable[[str, str], None]] = None,
        on_add_include_item: Optional[Callable[[str, str], None]] = None,
        on_remove_item: Optional[Callable[[str, str], None]] = None,
        on_set_item_mode: Optional[Callable[[str, str, str], None]] = None,
    ):
        self._active_platform = active_platform if active_platform in {"windows", "linux"} else "windows"
        self._on_add_item = on_add_item
        self._on_add_include_item = on_add_include_item
        self._on_remove_item = on_remove_item
        self._on_set_item_mode = on_set_item_mode
        platform_text = "Windows" if self._active_platform == "windows" else "Linux"
        exclusions = exclusions_by_platform.get(self._active_platform, [])
        inclusions = inclusions_by_platform.get(self._active_platform, [])
        self._rules: dict[str, str] = {}
        for name in exclusions:
            cleaned = (name or "").strip().lower()
            if cleaned:
                self._rules[cleaned] = "exclude"
        for name in inclusions:
            cleaned = (name or "").strip().lower()
            if cleaned:
                self._rules[cleaned] = "include"

        self._list_column = ft.Column(spacing=6)
        self._field = ft.TextField(
            hint_text="example.exe" if self._active_platform == "windows" else "example-binary",
            dense=True,
            expand=True,
            on_submit=self._add_exclude,
        )

        self._editor_surface = ft.Container(
            content=ft.Row(
                controls=[
                    self._field,
                    ft.IconButton(
                        icon=ft.Icons.DO_NOT_DISTURB,
                        tooltip="Add as exclude",
                        icon_color="#FF8A80",
                        on_click=self._add_exclude,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                        tooltip="Add as include",
                        icon_color="#81C784",
                        on_click=self._add_include,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="#151922",
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=10, vertical=8),
            border=ft.border.all(1, "#2A303C"),
        )

        self.wait_toggle = ToggleSettingItem(
            ft.Icons.TIMER,
            "teal_700",
            "Wait until app closes",
            value=wait_until_app_close_enabled,
            on_change=on_wait_until_app_close_change,
        )

        label_suffix = "(.exe)" if self._active_platform == "windows" else "(executable names)"
        self._list_label = ft.Text(
            f"{platform_text} process list {label_suffix}",
            size=12,
            weight="w600",
            color=COLOR_TEXT_PRIMARY,
        )

        header_icon = ft.Container(
            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=18, color="#9BC7FF"),
            width=34,
            height=34,
            border_radius=12,
            alignment=ft.Alignment.CENTER,
            bgcolor="#1B2330",
            border=ft.border.all(1, "#2D3A4F"),
        )

        header_text = ft.Column(
            controls=[
                ft.Text(
                    "Automatic Mode Settings",
                    color=COLOR_TEXT_PRIMARY,
                    size=14,
                    weight="w600",
                ),
                ft.Text(
                    "Auto: fullscreen apps open Low Latency; includes force open, excludes skip.",
                    size=12,
                    color=COLOR_DISABLED,
                ),
            ],
            spacing=2,
            expand=True,
        )

        platform_chip = ft.Container(
            content=ft.Text(platform_text, size=11, weight="w600", color="#BFD7FF"),
            bgcolor="#1B2330",
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border=ft.border.all(1, "#2D3A4F"),
        )

        tile_border = ft.RoundedRectangleBorder(
            radius=18,
            side=ft.BorderSide(width=1, color="#2A303C"),
        )

        controls_column = ft.Column(
            controls=[
                self.wait_toggle,
                ft.Container(
                    content=ft.Text(
                        "When enabled, Low Latency stays active until the matched app closes.",
                        size=11,
                        color=COLOR_DISABLED,
                    ),
                    padding=ft.padding.only(left=14, right=10, bottom=2),
                ),
                ft.Divider(height=1, color="#24303D"),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self._list_label,
                            self._editor_surface,
                            self._list_column,
                        ],
                        spacing=8,
                    ),
                    padding=ft.padding.symmetric(horizontal=8, vertical=6),
                ),
            ],
            spacing=10,
        )

        self._render_rules()

        super().__init__(
            title=ft.Container(
                content=ft.Row(
                    controls=[header_icon, header_text], #, platform_chip
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.only(top=4, bottom=4),
            ),
            bgcolor="#10141B",
            collapsed_bgcolor="#10141B",
            shape=tile_border,
            collapsed_shape=tile_border,
            text_color=COLOR_TEXT_PRIMARY,
            collapsed_text_color=COLOR_TEXT_PRIMARY,
            icon_color="#9BC7FF",
            collapsed_icon_color="#9BC7FF",
            controls=[
                ft.Container(
                    content=controls_column,
                    padding=ft.padding.only(top=6, bottom=2),
                ),
            ],
        )

    def _normalize(self, value: str) -> str:
        return (value or "").strip().lower()

    def _add_exclude(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        self._rules[value] = "exclude"
        if self._on_add_item:
            self._on_add_item(self._active_platform, value)
        self._field.value = ""
        self._render_rules()
        self.update()

    def _add_include(self, e):
        value = self._normalize(self._field.value)
        if not value:
            return
        self._rules[value] = "include"
        if self._on_add_include_item:
            self._on_add_include_item(self._active_platform, value)
        self._field.value = ""
        self._render_rules()
        self.update()

    def _remove_rule(self, value: str) -> None:
        if value not in self._rules:
            return
        del self._rules[value]
        if self._on_remove_item:
            self._on_remove_item(self._active_platform, value)
        self._render_rules()
        self.update()

    def _set_rule_mode(self, value: str, mode: str) -> None:
        if value not in self._rules or mode not in {"exclude", "include"}:
            return
        if self._rules[value] == mode:
            return
        self._rules[value] = mode
        if self._on_set_item_mode:
            self._on_set_item_mode(self._active_platform, value, mode)
        self._render_rules()
        self.update()

    def _build_mode_chip(self, value: str, mode: str, selected: bool) -> ft.Container:
        return ft.Container(
            content=ft.Text(mode.capitalize(), size=11, weight="w600", color="white" if selected else COLOR_TEXT_PRIMARY),
            bgcolor="#1976D2" if selected else "#2B2F3A",
            border=ft.border.all(1, "#4FC3F7" if selected else "#3B3F4A"),
            border_radius=999,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            ink=True,
            on_click=lambda e, name=value, target_mode=mode: self._set_rule_mode(name, target_mode),
        )

    def _render_rules(self) -> None:
        if not self._rules:
            self._list_column.controls = [
                ft.Container(
                    content=ft.Text("No entries.", size=12, color=COLOR_DISABLED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    bgcolor="#12161E",
                    border_radius=12,
                    border=ft.border.all(1, "#2A303C"),
                )
            ]
            return

        controls = []
        for item in sorted(self._rules.keys()):
            mode = self._rules[item]
            row = ft.Row(
                controls=[
                    ft.Text(item, size=13, color=COLOR_TEXT_PRIMARY, expand=True),
                    self._build_mode_chip(item, "exclude", mode == "exclude"),
                    self._build_mode_chip(item, "include", mode == "include"),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        tooltip="Remove",
                        icon_color=COLOR_DISABLED,
                        on_click=lambda e, name=item: self._remove_rule(name),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            controls.append(
                ft.Container(
                    content=row,
                    bgcolor="#12161E",
                    border_radius=12,
                    padding=ft.padding.only(left=10, right=6, top=4, bottom=4),
                    border=ft.border.all(1, "#2A303C"),
                )
            )

        self._list_column.controls = controls

    def set_rules(self, platform: str, exclusions: list[str], inclusions: list[str]) -> None:
        target = (platform or "").strip().lower()
        if target == self._active_platform:
            self._rules = {}
            for name in exclusions:
                normalized = self._normalize(name)
                if normalized:
                    self._rules[normalized] = "exclude"
            for name in inclusions:
                normalized = self._normalize(name)
                if normalized:
                    self._rules[normalized] = "include"
            self._render_rules()
        self.update()

    def set_wait_until_app_close(self, enabled: bool) -> None:
        self.wait_toggle.switch.value = bool(enabled)
        self.wait_toggle.switch.update()
