"""Display the available-update notification and its actions."""

from utils.i18n import t

import webbrowser

import flet as ft

from ..constants import GITHUB_URL
from utils.user_preferences import suppress_update_notification


def show_update_notification(page: ft.Page, latest_ver: str) -> None:
    if not latest_ver:
        return

    def on_dont_show_again_change(e):
        if e.control.value:
            suppress_update_notification(latest_ver)

    def on_update_click(e):
        webbrowser.open(GITHUB_URL)
        snack_bar.open = False
        page.update()

    snack_bar = ft.SnackBar(
        content=ft.Row(
            controls=[
                ft.Text(
                    t("update.available", version=latest_ver),
                    color="white",
                    expand=True,
                    no_wrap=False,
                ),
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            label=None,
                            value=False,
                            fill_color="white",
                            check_color="#171717",
                            width=20,
                            height=20,
                            on_change=on_dont_show_again_change,
                        ),
                        ft.Text(
                            t("update.hide"),
                            color="white",
                            size=12,
                            no_wrap=False,
                        ),
                    ],
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.ElevatedButton(
                    t("update.download"),
                    icon=ft.Icons.DOWNLOAD,
                    on_click=on_update_click,
                    style=ft.ButtonStyle(
                        color="white",
                        bgcolor="#2E7D32",
                    ),
                ),
            ],
            spacing=10,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        duration=10000,
        bgcolor="#171717",
        show_close_icon=True,
        close_icon_color="white"
    )
    page.overlay.append(snack_bar)
    snack_bar.open = True
    page.update()
