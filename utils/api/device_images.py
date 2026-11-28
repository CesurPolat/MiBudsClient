"""Cache validated device images and restore the last displayed preview."""

import hashlib
import io
import json
import math
import re
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from PIL import Image

from .http import resolve_api_url, retry_after


_IMAGE_SIZE_LIMIT = 8 * 1024 * 1024


class DeviceImageCache:
    def __init__(self, base_url: str, directory: Path, app_version: str, transport, clock):
        self.base_url = base_url
        self.directory = directory
        self.image_directory = directory / "assets" / "images"
        self.app_version = app_version
        self._transport = transport
        self._clock = clock
        self._image_lock = threading.Lock()
        self._image_retries = {}
        self._image_rate_limit_until = 0.0

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
        url = resolve_api_url(self.base_url, path)
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        target = (self.image_directory / f"{key}.png").resolve()
        with self._image_lock:
            try:
                with target.open("rb") as source:
                    body = source.read(_IMAGE_SIZE_LIMIT + 1)
                if len(body) > _IMAGE_SIZE_LIMIT:
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
                with self._transport(request, timeout=10) as response:
                    if response.headers.get_content_type() != "image/png":
                        raise ValueError("API returned non-PNG content")
                    body = response.read(_IMAGE_SIZE_LIMIT + 1)
                if len(body) > _IMAGE_SIZE_LIMIT:
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
                    delay = max(delay, retry_after(exc.headers.get("Retry-After"), self._clock, default=60))
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
        target = (self.image_directory / filename).resolve()
        try:
            with target.open("rb") as source:
                body = source.read(_IMAGE_SIZE_LIMIT + 1)
            if len(body) > _IMAGE_SIZE_LIMIT:
                return ""
            self._validate_image(body)
            return str(target)
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            return ""

    def remember_device_image(self, name: str, image_path: str) -> None:
        """Save the last displayed model image separately from catalog versions."""
        directory = self.image_directory.resolve()
        target = Path(image_path).resolve()
        if target.parent != directory or not self._read_saved_image(target.name):
            return
        record = self.directory / "last_device.json"
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

    def load_last_device_image(self, catalog: dict | None) -> tuple[str, str]:
        """Restore a local preview without discovery or network requests."""
        try:
            record = json.loads((self.directory / "last_device.json").read_text(encoding="utf-8"))
            if record.get("base_url") == self.base_url and isinstance(record.get("name"), str):
                image_path = self._read_saved_image(record.get("image_file"))
                if image_path:
                    return record["name"], image_path
        except (OSError, ValueError, TypeError, AttributeError):
            pass

        # Existing image caches predate the last-device record. Recover their
        # most recently downloaded valid image for the first upgraded launch.
        try:
            directory = self.image_directory
            candidates = sorted(directory.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)
            for candidate in candidates:
                image_path = self._read_saved_image(candidate.name)
                if not image_path:
                    continue
                name = ""
                if catalog:
                    for model in catalog["result"]["tw_product_list"]:
                        for icon in model.get("icon_static", []):
                            try:
                                url = resolve_api_url(self.base_url, icon["icon_url"])
                            except ValueError:
                                continue
                            if hashlib.sha256(url.encode("utf-8")).hexdigest() + ".png" == candidate.name:
                                name = model["name"]
                self.remember_device_image(name, image_path)
                return name, image_path
        except OSError:
            pass
        return "", ""
