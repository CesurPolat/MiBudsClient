"""Read-only MiBuds catalog client with verified, persistent offline cache."""

import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from PIL import Image


API_BASE_URL = os.getenv("MIBUDS_API_URL", "http://mibuds-api.cesurpolat.dev").rstrip("/")
_VERSION = re.compile(r"sha256-[0-9a-f]{64}\Z")


def cache_directory() -> Path:
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "MiBudsClient" / "catalog"


def validate_catalog(catalog: dict) -> dict:
    """Validate fields consumed by lookup/UI without discarding raw metadata."""
    if not isinstance(catalog, dict) or catalog.get("code") != 0:
        raise ValueError("Invalid catalog response")
    result = catalog.get("result")
    products = result.get("tw_product_list") if isinstance(result, dict) else None
    if not isinstance(products, list) or not products:
        raise ValueError("Catalog has no models")
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("Invalid model")
        for key in ("vid", "pid"):
            if not isinstance(product.get(key), str) or not re.fullmatch(r"[0-9a-fA-F]{1,4}", product[key]):
                raise ValueError("Invalid model identity")
        for key in ("name", "model"):
            if not isinstance(product.get(key), str) or not product[key].strip():
                raise ValueError("Invalid model name")
        if not isinstance(product.get("extra_info", {}), dict):
            raise ValueError("Invalid model metadata")
        if not isinstance(product.get("func_list", []), list):
            raise ValueError("Invalid function list")
        for key in ("icon_static", "icon_dynamic", "icon_guide"):
            icons = product.get(key, [])
            if not isinstance(icons, list) or any(
                not isinstance(icon, dict) or not isinstance(icon.get("icon_url"), str)
                for icon in icons
            ):
                raise ValueError("Invalid model assets")
    return catalog


def parse_extra_data(value) -> dict:
    """Decode function metadata on demand; retain strings in the raw catalog."""
    try:
        parsed = json.loads(value) if isinstance(value, str) else None
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


class CatalogClient:
    def __init__(self, *, base_url=API_BASE_URL, cache_dir=None, app_version="", clock=time.time):
        self.base_url = base_url.rstrip("/") + "/"
        if urlsplit(self.base_url).scheme not in {"http", "https"}:
            raise ValueError("API URL must use HTTP or HTTPS")
        self.cache_file = Path(cache_dir if cache_dir is not None else cache_directory()) / "catalog.json"
        install_directory = self.cache_file.parent if cache_dir is not None else self.cache_file.parent.parent
        self.install_id_file = install_directory / "install_id.txt"
        self.install_id = self._load_or_create_install_id()
        self.app_version = app_version.lstrip("v")
        self._clock = clock
        self._lock = threading.Lock()
        self._image_lock = threading.Lock()
        self._image_retries = {}
        self._image_rate_limit_until = 0.0
        self.catalog = None
        self.version = None
        self._catalog_text = None
        self.next_check_at = 0.0
        self._failures = 0
        self._terminal_error = False
        self.last_error = ""
        self._load_cache()

    def _load_or_create_install_id(self) -> str | None:
        """Reuse a random installation UUID independently of the catalog cache."""
        try:
            existing = UUID(self.install_id_file.read_text(encoding="ascii").strip())
            if existing.version == 4:
                return str(existing)
        except (OSError, ValueError):
            pass

        install_id = str(uuid4())
        temporary = self.install_id_file.with_suffix(".tmp")
        try:
            self.install_id_file.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(install_id, encoding="ascii")
            temporary.replace(self.install_id_file)
            return install_id
        except OSError:
            # Do not send a different transient ID on each launch if saving fails.
            return None
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def resolve_asset_url(self, path: str) -> str:
        url = urljoin(self.base_url, path)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != urlsplit(self.base_url).netloc:
            raise ValueError("Asset URL must belong to the MiBuds API")
        return url

    @staticmethod
    def _validate_image(body: bytes) -> None:
        with Image.open(io.BytesIO(body)) as image:
            if image.format != "PNG" or not (0 < image.width <= 4096 and 0 < image.height <= 4096):
                raise ValueError("Invalid device PNG")
            image.verify()

    @property
    def next_image_retry_at(self) -> float | None:
        deadlines = [deadline for _, deadline in self._image_retries.values()
                     if math.isfinite(deadline) and deadline > self._clock()]
        return min(deadlines) if deadlines else None

    def cache_image(self, path: str) -> str:
        """Return a validated local PNG, downloading each asset URL only once."""
        url = self.resolve_asset_url(path)
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        target = (self.cache_file.parent / "assets" / "images" / f"{key}.png").resolve()
        size_limit = 8 * 1024 * 1024
        with self._image_lock:
            try:
                with target.open("rb") as source:
                    body = source.read(size_limit + 1)
                if len(body) > size_limit:
                    raise ValueError("Cached image is too large")
                self._validate_image(body)
                return str(target)
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                pass

            failures, retry_at = self._image_retries.get(url, (0, 0))
            if self._clock() < max(retry_at, self._image_rate_limit_until):
                return ""
            temporary = target.with_suffix(".tmp")
            try:
                request = Request(url, headers={
                    "Accept": "image/png", "User-Agent": f"MiBudsClient/{self.app_version or 'dev'}",
                })
                with urlopen(request, timeout=10) as response:
                    if response.headers.get_content_type() != "image/png":
                        raise ValueError("API returned non-PNG content")
                    body = response.read(size_limit + 1)
                if len(body) > size_limit:
                    raise ValueError("Device image is too large")
                self._validate_image(body)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary.write_bytes(body)
                temporary.replace(target)
                self._image_retries.pop(url, None)
                return str(target)
            except HTTPError as exc:
                delay = min(21600, 60 * 2 ** min(failures, 9))
                if exc.code in {400, 404, 405}:
                    delay = math.inf
                elif exc.code == 429:
                    delay = max(delay, self._retry_after(exc.headers.get("Retry-After")))
                    self._image_rate_limit_until = self._clock() + delay
                exc.close()
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                delay = min(21600, 60 * 2 ** min(failures, 9))
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            self._image_retries[url] = (failures + 1, self._clock() + delay)
            return ""

    def _read_saved_image(self, filename: str) -> str:
        if not isinstance(filename, str) or not re.fullmatch(r"[0-9a-f]{64}\.png", filename):
            return ""
        target = (self.cache_file.parent / "assets" / "images" / filename).resolve()
        try:
            with target.open("rb") as source:
                body = source.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                return ""
            self._validate_image(body)
            return str(target)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            return ""

    def remember_device_image(self, name: str, image_path: str) -> None:
        """Save the last displayed model image separately from catalog versions."""
        directory = (self.cache_file.parent / "assets" / "images").resolve()
        target = Path(image_path).resolve()
        if target.parent != directory or not self._read_saved_image(target.name):
            return
        record = self.cache_file.parent / "last_device.json"
        temporary = record.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps({
                "base_url": self.base_url, "name": name, "image_file": target.name,
            }, ensure_ascii=False), encoding="utf-8")
            temporary.replace(record)
        except OSError:
            pass
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def load_last_device_image(self) -> tuple[str, str]:
        """Restore a local preview without discovery or network requests."""
        try:
            record = json.loads((self.cache_file.parent / "last_device.json").read_text(encoding="utf-8"))
            if record.get("base_url") == self.base_url and isinstance(record.get("name"), str):
                image_path = self._read_saved_image(record.get("image_file"))
                if image_path:
                    return record["name"], image_path
        except (OSError, ValueError, TypeError, AttributeError):
            pass

        # Existing image caches predate the last-device record. Recover their
        # most recently downloaded valid image for the first upgraded launch.
        try:
            directory = self.cache_file.parent / "assets" / "images"
            candidates = sorted(directory.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)
            for candidate in candidates:
                image_path = self._read_saved_image(candidate.name)
                if not image_path:
                    continue
                name = ""
                if self.catalog:
                    for model in self.catalog["result"]["tw_product_list"]:
                        for icon in model.get("icon_static", []):
                            try:
                                url = self.resolve_asset_url(icon["icon_url"])
                            except ValueError:
                                continue
                            if hashlib.sha256(url.encode("utf-8")).hexdigest() + ".png" == candidate.name:
                                name = model["name"]
                self.remember_device_image(name, image_path)
                return name, image_path
        except OSError:
            pass
        return "", ""

    @staticmethod
    def _verified_catalog(text: str, version: str) -> dict:
        if not isinstance(version, str) or not _VERSION.fullmatch(version):
            raise ValueError("Invalid catalog version")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != version[7:]:
            raise ValueError("Catalog SHA-256 mismatch")
        return validate_catalog(json.loads(text.lstrip("\ufeff")))

    def _load_cache(self) -> None:
        try:
            cached = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if cached.get("base_url") != self.base_url:
                return
            catalog = self._verified_catalog(cached["catalog_text"], cached["version"])
            next_check = float(cached.get("next_check_at", 0))
            if not math.isfinite(next_check):
                raise ValueError("Invalid cache schedule")
            self.catalog, self.version = catalog, cached["version"]
            self._catalog_text = cached["catalog_text"]
            self.next_check_at = next_check
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def _save_cache(self) -> None:
        if self.catalog is None:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "base_url": self.base_url, "version": self.version,
                "catalog_text": self._catalog_text, "next_check_at": self.next_check_at,
            }, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.cache_file)
        except OSError:
            # A read-only cache must not discard a working in-memory catalog.
            pass

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
        with urlopen(request, timeout=10) as response:
            if response.headers.get_content_type() != "application/json":
                raise ValueError("API returned non-JSON content")
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise ValueError("Catalog response is too large")
            return body

    def _retry_after(self, value: str | None) -> float:
        try:
            delay = float(value)
            if math.isfinite(delay):
                return max(0, delay)
        except (ValueError, TypeError):
            try:
                return max(0, parsedate_to_datetime(value).timestamp() - self._clock())
            except (ValueError, TypeError, OverflowError):
                pass
        return 60

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
                version = check["version"]
                if check.get("schema_version") != 1 or not isinstance(version, str) or not _VERSION.fullmatch(version):
                    raise ValueError("Invalid catalog check response")
                if check.get("sha256") != version[7:]:
                    raise ValueError("Inconsistent catalog hash")
                interval = check.get("check_interval_seconds", 21600)
                if type(interval) is not int or interval <= 0:
                    raise ValueError("Invalid check interval")
                changed = self.catalog is None or self.version != version
                if changed:
                    text = self._get(check["catalog_url"]).decode("utf-8")
                    catalog = self._verified_catalog(text, version)
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
                delay = max(backoff, self._retry_after(exc.headers.get("Retry-After"))) if exc.code == 429 else backoff
                self.next_check_at = self._clock() + delay
                self.last_error = f"MiBuds API: HTTP {exc.code}"
                exc.close()
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                self._failures += 1
                self.next_check_at = self._clock() + min(21600, 60 * 2 ** min(self._failures - 1, 9))
                self.last_error = f"MiBuds catalog: {exc}"
            self._save_cache()
            return False
