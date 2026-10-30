"""Synchronize API metadata off the Flet and Bluetooth listener threads."""

import threading
import time
import re
from urllib.parse import unquote, urlsplit

from controllers.bluetooth.capabilities import resolve_capabilities
from controllers.bluetooth.device_catalog import get_device_models_by_name, install_catalog
from utils.mibuds_api import CatalogClient


class CatalogSync:
    def __init__(self, *, publish, get_identity, app_version, client=None, get_device_name=lambda: ""):
        self.client = client if client is not None else CatalogClient(app_version=app_version)
        self._publish = publish
        self._get_identity = get_identity
        self._get_device_name = get_device_name
        self._wake = threading.Event()
        self._stopped = threading.Event()
        self._thread = None
        self.cached_device = self.client.load_last_device_image()
        self._last_presentation = self.cached_device if self.cached_device[1] else None
        self._awaiting_first_device = True
        self._last_capabilities = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stopped.set()
        self._wake.set()

    def identity_changed(self, identity):
        # The listener only queues work; it never performs HTTP requests.
        self._wake.set()

    def _publish_device(self):
        identity = self._get_identity()
        device_name = self._get_device_name()
        if identity is not None or device_name:
            self._awaiting_first_device = False
        elif self._awaiting_first_device and self._last_presentation:
            return
        if identity is not None:
            models = identity.models
        else:
            models = get_device_models_by_name(device_name)
        capabilities = resolve_capabilities(device_name, identity)
        if capabilities != self._last_capabilities:
            self._last_capabilities = capabilities
            self._publish({"type": "capabilities_changed"})
        normalized_name = " ".join(device_name.split()).casefold()
        model = next((item for item in models
                      if " ".join(item["name"].split()).casefold() == normalized_name),
                     models[0] if models else None)
        image_url = ""
        if model:
            icons = model.get("icon_static", [])
            color = model.get("extra_info", {}).get("default_color")
            def image_priority(icon):
                filename = unquote(urlsplit(icon["icon_url"]).path).casefold()
                is_black = "black" in re.split(r"[^a-z0-9]+", filename)
                return (not is_black, icon.get("color") != color)

            # Color IDs vary by model; the catalog asset name identifies black.
            ordered_icons = sorted(icons, key=image_priority)
            for icon in ordered_icons:
                if not icon["icon_url"].strip():
                    continue
                try:
                    image_url = self.client.resolve_asset_url(icon["icon_url"])
                    break
                except ValueError:
                    continue
        image_path = self.client.cache_image(image_url) if image_url else ""
        presentation = (model["name"] if model else "", image_path)
        if presentation != self._last_presentation:
            if image_path:
                self.client.remember_device_image(presentation[0], image_path)
            self._publish({"type": "catalog_device", "name": presentation[0], "image_path": image_path})
            self._last_presentation = presentation

    def _run(self):
        if self.client.catalog is not None:
            install_catalog(self.client.catalog)
        self._publish_device()
        while not self._stopped.is_set():
            self._wake.clear()
            identity = self._get_identity()
            changed = self.client.refresh(
                identity.vid if identity else None,
                identity.pid if identity else None,
            )
            if self._stopped.is_set():
                return
            if changed:
                install_catalog(self.client.catalog)
            if self.client.last_error:
                print(self.client.last_error)
            self._publish_device()
            next_check = self.client.next_check_at
            if self.client.next_image_retry_at is not None:
                next_check = min(next_check, self.client.next_image_retry_at)
            delay = max(1, next_check - time.time())
            self._wake.wait(min(delay, 21600))
