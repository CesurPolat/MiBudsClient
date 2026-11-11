"""Connection feedback styled to match the home control panel."""

from utils.i18n import Message, t, render

import flet as ft
from ..constants import HOME_CONTROLS_HEIGHT

class ConnectionPanel(ft.Column):
    def __init__(self):
        self._failure_reason = ""
        self.connection_label = ft.Text(t("connection.connecting"), size=18, color="white", weight="w500",
                                        text_align=ft.TextAlign.CENTER)
        self.connection_progress = ft.ProgressRing(width=28, height=28, stroke_width=3, color="white")
        self.connection_reason = ft.Text(
            size=12, color="white70", visible=False, selectable=True,
            text_align=ft.TextAlign.CENTER, max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.retry_button = ft.TextButton(
            content=ft.Text(t("connection.retry")), icon=ft.Icons.REFRESH, visible=False,
            style=ft.ButtonStyle(color="white"),
        )
        self._progress_slot = ft.Container(
            content=self.connection_progress, height=28, alignment=ft.Alignment.CENTER)
        self._reason_slot = ft.Container(
            content=ft.Column([self.connection_reason], scroll=ft.ScrollMode.AUTO,
                              alignment=ft.MainAxisAlignment.CENTER,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            height=64, alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(horizontal=16), visible=False)
        self._retry_slot = ft.Container(
            content=self.retry_button, height=36, alignment=ft.Alignment.CENTER, visible=False)
        super().__init__(controls=[
            ft.Container(content=ft.Container(content=ft.Icon(ft.Icons.BLUETOOTH, size=28, color="white"),
                         width=52, height=52, border_radius=16, bgcolor="#23364C",
                         alignment=ft.Alignment.CENTER), height=52, alignment=ft.Alignment.CENTER),
            self._progress_slot,
            ft.Container(content=self.connection_label, alignment=ft.Alignment.CENTER),
            self._reason_slot,
            self._retry_slot,
        ], spacing=12, height=HOME_CONTROLS_HEIGHT - 12,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def update_connection_state(self, state: str, reason: str = "") -> None:
        connecting = state in {"connecting", "retrying", "loading"}
        failed = state == "failed"
        if failed and reason:
            self._failure_reason = reason
        elif state in {"connected", "loading"}:
            self._failure_reason = ""
        # Automatic retries must not replace the actionable failure with a
        # countdown or briefly hide it while the next connection is attempted.
        display_reason = self._failure_reason if state in {"connecting", "retrying"} and self._failure_reason else reason
        self.connection_label.value = {
            "connecting": t("connection.connecting"),
            "retrying": t("connection.connecting"),
            "loading": t("eq.reading"),
            "connected": t("connection.connected"),
            "failed": t("connection.failed"),
        }.get(state, t("connection.waiting"))
        self.connection_label.color = "white"
        self.connection_progress.visible = connecting
        self._progress_slot.visible = connecting
        short_reason = display_reason
        if isinstance(display_reason, Message) and display_reason.key == "connection.technical":
            short_reason = display_reason.params.get("reason", display_reason)
        self.connection_reason.value = render(short_reason)
        self.connection_reason.tooltip = render(display_reason) if display_reason else None
        self.connection_reason.visible = bool(display_reason)
        self._reason_slot.visible = bool(display_reason)
        self.retry_button.visible = failed
        self._retry_slot.visible = failed
        self.retry_button.disabled = connecting
