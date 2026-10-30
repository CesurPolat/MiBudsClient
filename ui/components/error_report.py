"""Flet consent dialog; no delivery occurs before the Send action."""
import copy
import json
import threading
from functools import wraps

import flet as ft
from utils.i18n import t
from utils.error_reports import encode_report, redact
from ui.constants import COLOR_CARD_BG, COLOR_TEXT_PRIMARY, CARD_BORDER_RADIUS


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class ErrorReportDialog:
    def __init__(self, page, queue, *, ui_lock=None):
        self.page, self.queue = page, queue
        self.pending = []
        self.active = None
        self.snack = None
        self._lock = ui_lock if ui_lock is not None else threading.RLock()

    @serialized
    def receive(self, report):
        if len(self.pending) < 20:
            self.pending.append(copy.deepcopy(report))
        self.show_pending()

    @serialized
    def show_pending(self):
        if self.active is not None or not self.pending or self.page.window.visible is False:
            return
        report = self.pending.pop(0)
        description = ft.TextField(label=t('report.description'), multiline=True,
                                   min_lines=3, max_lines=5, max_length=4000)
        preview = ft.Text('', selectable=True, size=11)
        feedback = ft.Text('', color=ft.Colors.RED, visible=False)
        def synchronized(callback):
            @wraps(callback)
            def call(e=None):
                with self._lock:
                    return callback(e)
            return call

        @synchronized
        def update_preview(e=None):
            report['details']['description'] = redact(description.value or '')[:4000]
            preview.value = json.dumps(report, ensure_ascii=False, indent=2)
            if e is not None:
                self.page.update()
        description.on_change = update_preview
        update_preview()

        @synchronized
        def close(e=None):
            dialog.open = False
            # Keep the control mounted until Flutter acknowledges dismissal.
            # Removing an open dialog from overlay leaves its native route alive.
            dialog.update()

        @synchronized
        def dismissed(e):
            if self.active is dialog:
                self.active = None
            self.show_pending()

        @synchronized
        def send(e):
            if send_button.disabled:
                return
            send_button.disabled = True
            try:
                update_preview()
                encode_report(report)
                saved = self.queue.enqueue(copy.deepcopy(report))
            except Exception:
                saved = False
            if saved:
                close()
                self.status('queued')
            else:
                # Retain the user's description and allow another attempt.
                send_button.disabled = False
                feedback.value = t('report.failed')
                feedback.visible = True
                dialog.update()

        send_button = ft.ElevatedButton(t('report.send'), on_click=send)
        dialog = ft.AlertDialog(
            modal=True, title=ft.Text(t('report.title')),
            content=ft.Container(width=420, content=ft.Column([
                ft.Text(t('report.consent')), description, ft.Text(t('report.privacy'), size=12),
                ft.ExpansionTile(title=ft.Text(t('report.preview')), controls=[preview]),
                feedback,
            ], tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton(t('report.cancel'), on_click=close), send_button],
        )
        self.active = dialog
        dialog.on_dismiss = dismissed
        self.page.show_dialog(dialog)

    @serialized
    def status(self, state):
        if self.snack is not None and self.snack.open:
            self.snack.open = False
            self.snack.update()
        snack = ft.SnackBar(
            content=ft.Text(t('report.' + state), color=COLOR_TEXT_PRIMARY),
            bgcolor=COLOR_CARD_BG,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=CARD_BORDER_RADIUS),
        )
        self.snack = snack
        self.page.show_dialog(snack)
