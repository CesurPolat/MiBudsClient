"""Public MiBuds API and catalog synchronization."""

import json
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .catalog_data import parse_extra_data, validate_catalog, validate_catalog_check, verify_catalog
from .catalog_store import CatalogStore, cache_directory
from .device_images import DeviceImageCache
from .error_reporting import DeliveryError, ErrorReportClient, encode_report
from .http import API_BASE_URL, resolve_api_url, retry_after

__all__ = [
    "API_BASE_URL",
    "CatalogClient",
    "DeliveryError",
    "ErrorReportClient",
    "cache_directory",
    "encode_report",
    "parse_extra_data",
    "validate_catalog",
]


class CatalogClient:
    def __init__(self, *, base_url=API_BASE_URL, cache_dir=None, app_version="", clock=time.time):
        self.base_url = base_url.rstrip("/") + "/"
        if urlsplit(self.base_url).scheme not in {"http", "https"}:
            raise ValueError("API URL must use HTTP or HTTPS")
        self._store = CatalogStore(self.base_url, Path(cache_dir) if cache_dir is not None else None)
        self.cache_file = self._store.cache_file
        self.install_id_file = self._store.install_id_file
        self.install_id = self._store.load_or_create_install_id()
        self.app_version = app_version.lstrip("v")
        self._clock = clock
        self._lock = threading.Lock()
        self._images = DeviceImageCache(
            self.base_url, self.cache_file.parent, self.app_version,
            self._open, clock,
        )
        self.catalog = None
        self.version = None
        self._catalog_text = None
        self.next_check_at = 0.0
        self._failures = 0
        self._terminal_error = False
        self.last_error = ""
        snapshot = self._store.load() or self._store.load_bundled()
        if snapshot is not None:
            self.catalog, self.version, self._catalog_text, self.next_check_at = snapshot

    def resolve_asset_url(self, path: str) -> str:
        return resolve_api_url(self.base_url, path)

    @property
    def next_image_retry_at(self) -> float | None:
        return self._images.next_image_retry_at

    def cache_image(self, path: str) -> str:
        return self._images.cache_image(path)

    def remember_device_image(self, name: str, image_path: str) -> None:
        self._images.remember_device_image(name, image_path)

    def load_last_device_image(self) -> tuple[str, str]:
        return self._images.load_last_device_image(self.catalog)

    def _save_cache(self) -> None:
        if self.catalog is not None:
            self._store.save(self.version, self._catalog_text, self.next_check_at)

    @staticmethod
    def _open(request: Request, *, timeout: float):
        return urlopen(request, timeout=timeout)

    def _get(self, path: str) -> bytes:
        url = self.resolve_asset_url(path)
        headers = {
            "Accept": "application/json",
            "User-Agent": f"MiBudsClient/{self.app_version or 'dev'}",
            "X-MiBuds-App-Version": self.app_version,
        }
        if self.install_id and urlsplit(url).path == "/v1/models/check":
            headers["X-MiBuds-Install-ID"] = self.install_id
        request = Request(url, headers=headers)
        with self._open(request, timeout=10) as response:
            if response.headers.get_content_type() != "application/json":
                raise ValueError("API returned non-JSON content")
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise ValueError("Catalog response is too large")
            return body

    def refresh(self, vid: int | None = None, pid: int | None = None) -> bool:
        """Check once when due; failures preserve the last verified catalog."""
        if (vid is None) != (pid is None) or any(
            value is not None and (not isinstance(value, int) or not 0 <= value <= 0xFFFF)
            for value in (vid, pid)
        ):
            raise ValueError("VID and PID must both be unsigned 16-bit integers")
        with self._lock:
            if self._terminal_error or self._clock() < self.next_check_at:
                return False
            params = {}
            if self.version:
                params["version"] = self.version
            if vid is not None:
                params.update(vid=f"{vid:04x}", pid=f"{pid:04x}")
            try:
                path = "/v1/models/check" + ("?" + urlencode(params) if params else "")
                check = json.loads(self._get(path))
                version, interval = validate_catalog_check(check)
                changed = self.catalog is None or self.version != version
                if changed:
                    text = self._get(check["catalog_url"]).decode("utf-8")
                    catalog = verify_catalog(text, version)
                    self.catalog, self.version, self._catalog_text = catalog, version, text
                self.next_check_at = self._clock() + max(60, interval)
                self.last_error = ""
                self._failures = 0
                self._save_cache()
                return changed
            except HTTPError as exc:
                if exc.code in {400, 404, 405}:
                    self._terminal_error = True
                self._failures += 1
                backoff = min(21600, 60 * 2 ** min(self._failures - 1, 9))
                delay = backoff
                if exc.code == 429:
                    delay = max(backoff, retry_after(exc.headers.get("Retry-After"), self._clock, default=60))
                self.next_check_at = self._clock() + delay
                self.last_error = f"MiBuds API: HTTP {exc.code}"
                exc.close()
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                self._failures += 1
                self.next_check_at = self._clock() + min(21600, 60 * 2 ** min(self._failures - 1, 9))
                self.last_error = f"MiBuds catalog: {exc}"
            self._save_cache()
            return False
