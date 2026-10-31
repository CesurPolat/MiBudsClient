"""Optional local post-auth capture for an explicitly enabled ANC test session."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_lock = threading.Lock()


def record(direction, data=None, **details):
    path = os.environ.get("MIBUDS_ANC_CAPTURE", "").strip()
    if not path:
        return
    entry = {"time": datetime.now(timezone.utc).isoformat(), "direction": direction, **details}
    if data is not None:
        entry["hex"] = data.hex(" ").upper()
    try:
        with _lock, Path(path).open("a", encoding="utf8") as stream:
            stream.write(json.dumps(entry) + "\n")
    except OSError as exc:
        # A diagnostic file failure must not terminate the Bluetooth session.
        print(f"[ANC capture] Could not write local capture: {exc}")
