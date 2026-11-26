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
