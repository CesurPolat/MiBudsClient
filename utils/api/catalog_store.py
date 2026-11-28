"""Persist installation identity and verified catalog snapshots."""

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

from ..app.resource_manager import get_resource_path
from .catalog_data import verify_catalog


def cache_directory() -> Path:
    if sys.platform == "win32":
        root = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "MiBudsClient" / "catalog"


class CatalogStore:
    def __init__(self, base_url: str, cache_dir: Path | None):
        self.base_url = base_url
        directory = cache_dir if cache_dir is not None else cache_directory()
        self.cache_file = directory / "catalog.json"
        install_directory = directory if cache_dir is not None else directory.parent
        self.install_id_file = install_directory / "install_id.txt"

    def load_or_create_install_id(self) -> str | None:
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

    def load(self) -> tuple[dict, str, str, float] | None:
        try:
            cached = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if cached.get("base_url") != self.base_url:
                return None
            catalog = verify_catalog(cached["catalog_text"], cached["version"])
            next_check = float(cached.get("next_check_at", 0))
            if not math.isfinite(next_check):
                raise ValueError("Invalid cache schedule")
            return catalog, cached["version"], cached["catalog_text"], next_check
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def load_bundled(self) -> tuple[dict, str, str, float] | None:
        """Seed the first check with the bundled catalog's exact UTF-8 hash."""
        try:
            # Preserve BOM and line endings, just as for downloaded catalogs.
            text = Path(get_resource_path("assets/device_catalog.json")).read_bytes().decode("utf-8")
            version = "sha256-" + hashlib.sha256(text.encode("utf-8")).hexdigest()
            catalog = verify_catalog(text, version)
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        return catalog, version, text, 0.0

    def save(self, version: str, text: str, next_check_at: float) -> None:
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "base_url": self.base_url, "version": version,
                "catalog_text": text, "next_check_at": next_check_at,
            }, ensure_ascii=False), encoding="utf-8")
            temporary.replace(self.cache_file)
        except OSError:
            # A read-only cache must not discard a working in-memory catalog.
            pass
