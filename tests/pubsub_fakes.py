"""Wire UI topic callbacks to a mock page for existing unit tests."""

import asyncio
import threading

from ui.app_subscriptions import subscribe_ui_events
from ui.page_updates import refresh_page
from utils.app.app_shutdown import ApplicationShutdown


def subscribe_test_ui(*, page, window_manager, **kwargs):
    def publish(topic, /, **message):
        page.pubsub.send_all_on_topic(topic.value, message)

    def update_ui():
        refresh_page(page, window_manager, sync_tray=sync_tray)

    sync_tray = subscribe_ui_events(
        page=page, window_manager=window_manager, publish=publish, update_ui=update_ui,
        ui_lock=threading.RLock(), shutdown=ApplicationShutdown(), **kwargs,
    )
    callbacks = dict(item.args for item in page.pubsub.subscribe_topic.call_args_list)

    def deliver(topic, **message):
        callback = callbacks.get(topic)
        if callback is not None:
            asyncio.run(callback(topic, message))

    return deliver
