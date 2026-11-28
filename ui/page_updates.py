"""Refresh the Flet page and its desktop presentation."""

from .localization import refresh_translations


def refresh_page(page, window_manager, *, sync_tray=None) -> None:
    """Apply the shared refresh sequence from a serialized UI callback."""
    if sync_tray is not None:
        sync_tray()
    refresh_translations(page.controls)
    refresh_translations(page.overlay)
    page.update()
    window_manager.request_content_fit()
