"""Decode the existing Redmi battery values without changing the wire protocol."""


def battery_state(raw) -> tuple[int, bool] | None:
    """Return (percent, charging) only for a valid byte with a 0–100 level."""
    if type(raw) is not int or not 0 <= raw <= 255 or raw == 255:
        return None
    charging = raw >= 128
    percent = raw - 128 if charging else raw
    return (percent, charging) if percent <= 100 else None
