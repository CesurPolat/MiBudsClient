"""Connection feedback styled to match the home control panel."""

from utils.i18n import t, render

import flet as ft

class ConnectionPanel(ft.Column):
    def __init__(self):
        self.connection_label = ft.Text(t("connection.connecting"), size=18, color="white", weight="w500")
        self.connection_progress = ft.ProgressRing(width=32, height=32, stroke_width=3)
        self.connection_reason = ft.Text(
            size=12, color="orange", visible=False, selectable=True,
            text_align=ft.TextAlign.CENTER,
        )
        self.retry_button = ft.TextButton(
            content=ft.Text(t("connection.retry")), icon=ft.Icons.REFRESH, visible=False,
        )
        super().__init__(controls=[
            ft.Icon(ft.Icons.BLUETOOTH, size=40, color="blue"),
            self.connection_progress,
            self.connection_label,
            self.connection_reason,
            self.retry_button,
        ], spacing=14, height=280,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

    def update_connection_state(self, state: str, reason: str = "") -> None:
        connecting = state == "connecting"
        failed = state == "failed"
        self.connection_label.value = {
            "connecting": t("connection.connecting"),
            "connected": t("connection.connected"),
            "failed": t("connection.failed"),
        }.get(state, t("connection.waiting"))
        self.connection_label.color = "green" if state == "connected" else "orange"
        self.connection_progress.visible = connecting
        self.connection_reason.value = render(reason)
        self.connection_reason.visible = failed and bool(reason)
        self.retry_button.visible = failed
        self.retry_button.disabled = connecting
