"""Value-only implementation identity for reports; never execute Git at runtime."""
import hashlib
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def implementation_diagnostics():
    from ui.constants import APP_VERSION
    directory = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    try:
        for path in sorted(directory.rglob("*.py")):
            digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
        fingerprint = digest.hexdigest() if (directory / "controller.py").is_file() else None
    except OSError:
        fingerprint = None
    return {"app_version": APP_VERSION, "bluetooth_source_sha256": fingerprint}
