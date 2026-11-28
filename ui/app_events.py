"""Handle application-level UI topics."""

import time

from utils.app.i18n import LANGUAGE_CHOICES, is_rtl, set_language, t
from utils.app.user_preferences import set_language_preference

from .components.dialogs.update_notification import show_update_notification


class AppEvents:
    def __init__(self, *, page, settings, status_card, tray, window_manager, debug_console,
                 on_window_show, report_events, begin_shutdown, update_page):
        self._page = page
        self._settings = settings
        self._status_card = status_card
        self._tray = tray
        self._window_manager = window_manager
        self._debug_console = debug_console
        self._on_window_show = on_window_show
        self._report_events = report_events
        self._begin_shutdown = begin_shutdown
        self._update_page = update_page
        self._last_debug_toggle_at = 0.0

    def routes(self):
        return {
            "app": self.on_app,
            "window": self.on_window,
            "language": self.on_language,
            "update_notification": self.on_update_notification,
            "debug_console": self.on_debug_console,
        }

    def on_app(self, message):
        if message.get("action") == "close":
            if self._report_events is not None:
                self._report_events.stop()
            self._begin_shutdown()
            self._window_manager.close()

    def on_window(self, message):
        action = message.get("action")
        if action == "show":
            self._window_manager.apply_show()
            self._on_window_show()
            if self._report_events is not None:
                self._report_events.show_pending()
        elif action == "hide":
            self._window_manager.apply_hide()

    def on_language(self, message):
        language = message.get("language")
        if not isinstance(language, str) or language not in LANGUAGE_CHOICES:
            return
        set_language_preference(language)
        set_language(language)
        self._page.rtl = is_rtl()
        self._settings.language_selector.value = language
        self._tray.refresh_menu()
        self._update_page()

    def on_update_notification(self, message):
        show_update_notification(self._page, message.get("latest_ver"))

    def on_debug_console(self, message):
        if message.get("action") != "toggle":
            return
        now = time.monotonic()
        if now - self._last_debug_toggle_at < 0.35:
            return
        self._last_debug_toggle_at = now

        result = self._debug_console.toggle_console()
        if result == "opened":
            self._status_card.update_status(t("debug.opened"), "blue")
        elif result == "closed":
            self._status_card.update_status(t("debug.closed"), "white")
        else:
            self._status_card.update_status(t("debug.failed"), "red")
        self._update_page()
