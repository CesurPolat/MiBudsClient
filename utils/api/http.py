"""Shared URL and retry handling for MiBuds HTTP requests."""

import math
import os
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit


API_BASE_URL = os.getenv("MIBUDS_API_URL", "https://mibuds-api.cesurpolat.dev").rstrip("/")


def resolve_api_url(base_url: str, path: str) -> str:
    url = urljoin(base_url, path)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != urlsplit(base_url).netloc:
        raise ValueError("Asset URL must belong to the MiBuds API")
    return url


def retry_after(value: str | None, clock, default: float) -> float:
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = parsedate_to_datetime(value).timestamp() - clock()
        except (ValueError, TypeError, OverflowError):
            return default
    return max(0, delay) if math.isfinite(delay) else default
