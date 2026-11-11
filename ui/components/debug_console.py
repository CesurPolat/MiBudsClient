"""In-app Linux debug console; stream writers never touch Flet controls."""

import asyncio
import threading

import flet as ft

from utils.i18n import t
from ui.constants import COLOR_BG, COLOR_HOME_BORDER, COLOR_TEXT_PRIMARY
from ui.localization import refresh_translations


class DebugConsoleDialog:
    def __init__(self, page, manager, *, ui_lock=None):
        self.page = page
        self.manager = manager
        self._lock = ui_lock if ui_lock is not None else threading.RLock()
        self._revision = 0
        self._stopped = False
        self._closing = False
        self._snapshot = None
        self.text = ft.Text('', size=11, font_family='monospace', selectable=True,
                            color=COLOR_TEXT_PRIMARY, rtl=False)
        self.body = ft.Container(
            content=ft.Column([self.text], scroll=ft.ScrollMode.AUTO, expand=True,
                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=COLOR_BG, padding=12, border_radius=10,
            border=ft.Border.all(1, COLOR_HOME_BORDER),
        )
        self.dialog = ft.AlertDialog(
            title=ft.Text(t('debug.title'), size=17, weight=ft.FontWeight.W_600),
            content=self.body, bgcolor=COLOR_BG,
            actions=[
                ft.TextButton(t('debug.clear'), on_click=self.clear),
                ft.TextButton(t('debug.close'), on_click=self.close),
            ],
            on_dismiss=self._dismissed,
        )

    def _fit(self):
        width, height = self.page.width, self.page.height
        width = width if isinstance(width, (int, float)) else 655
        height = height if isinstance(height, (int, float)) else 400
        self.body.width = max(1, min(900, width - 80))
        self.body.height = max(1, min(480, height - 220))

    def _read(self):
        snapshot = self.manager.get_recent_logs(max_lines=1200)
        if snapshot == self._snapshot:
            return False
        self._snapshot = snapshot
        self.text.value = snapshot if snapshot else t('debug.empty')
        return True

    def toggle(self):
        with self._lock:
            if self._stopped:
                return 'failed'
            if self._closing:
                return 'closed'
            if self.dialog.open:
                self.close()
                return 'closed'
            self._revision += 1
            self._snapshot = None
            refresh_translations(self.dialog)
            self._read()
            self._fit()
            self.page.show_dialog(self.dialog)
            self.page.run_task(self._refresh_logs, self._revision)
            return 'opened'

    async def _refresh_logs(self, revision):
        while True:
            await asyncio.sleep(.4)
            with self._lock:
                if self._stopped or revision != self._revision or not self.dialog.open:
                    return
                try:
                    old_size = (self.body.width, self.body.height)
                    self._fit()
                    changed = self._read()
                    if changed or old_size != (self.body.width, self.body.height):
                        self.page.update()
                except RuntimeError as error:
                    if 'destroyed session' in str(error).lower():
                        return
                    raise

    def clear(self, _=None):
        with self._lock:
            if self._stopped:
                return
            self.manager.clear_logs()
            self._read()
            self.page.update()

    def close(self, _=None):
        with self._lock:
            if self._stopped:
                return
            self._closing = True
            self._revision += 1
            self.dialog.open = False
            self.page.update()

    def _dismissed(self, _=None):
        with self._lock:
            # Do not remove the route from overlay before Flutter dismisses it.
            self.dialog.open = False
            self._closing = False
            self._revision += 1

    def stop(self):
        with self._lock:
            self._stopped = True
            self._revision += 1
