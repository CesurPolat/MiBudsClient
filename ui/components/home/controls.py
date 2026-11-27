"""Connection and quick controls shown on Home."""

import flet as ft

from ...constants import (
    CARD_BORDER_RADIUS,
    COLOR_HOME_BORDER,
    COLOR_HOME_SURFACE,
    COLOR_HOME_SURFACE_TOP,
    HOME_CONTROLS_HEIGHT,
)
from .connection import ConnectionPanel


class HomeControls(ft.Container):
    def __init__(self, latency, noise, equalizer):
        self.connection_panel = ConnectionPanel()
        self.connection_card = self._card(self.connection_panel, height=HOME_CONTROLS_HEIGHT)
        self.latency_card = self._card(latency)
        self.noise_card = self._card(noise)
        self.equalizer_card = self._card(equalizer)
        self.connected_controls = ft.Column(
            spacing=8, visible=False, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        super().__init__(
            content=ft.Column(
                [self.connection_card, self.connected_controls],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def update_available_controls(
        self, *, connected: bool, latency: bool, noise: bool, equalizer: bool,
    ) -> None:
        controls = []
        for card, available in (
            (self.latency_card, latency),
            (self.noise_card, noise),
            (self.equalizer_card, equalizer),
        ):
            card.visible = card.content.visible = available
            if available:
                controls.append(card)
        self.connected_controls.controls = controls
        self.visible = not connected or bool(controls)

    def refresh_connection_panel(
        self, *, connected: bool, waiting_for_eq: bool, eq_failure_reason: str | None = None,
    ) -> None:
        ready = connected and not waiting_for_eq
        self.connection_card.visible = self.connection_panel.visible = not ready
        self.connected_controls.visible = ready
        if waiting_for_eq:
            if eq_failure_reason is None:
                self.connection_panel.update_connection_state("loading")
            else:
                self.connection_panel.update_connection_state("failed", eq_failure_reason)

    @staticmethod
    def _card(control, height=None):
        return ft.Container(
            content=control,
            height=height,
            bgcolor=COLOR_HOME_SURFACE,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[COLOR_HOME_SURFACE_TOP, COLOR_HOME_SURFACE],
            ),
            border=ft.Border.all(1, COLOR_HOME_BORDER),
            border_radius=CARD_BORDER_RADIUS,
            padding=6,
        )
