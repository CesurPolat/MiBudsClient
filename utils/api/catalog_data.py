"""Decode and validate MiBuds catalog data."""

import hashlib
import json
import re


_VERSION = re.compile(r"sha256-[0-9a-f]{64}\Z")


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


def verify_catalog(text: str, version: str) -> dict:
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError("Invalid catalog version")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != version[7:]:
        raise ValueError("Catalog SHA-256 mismatch")
    return validate_catalog(json.loads(text.lstrip("\ufeff")))


def validate_catalog_check(check: dict) -> tuple[str, int]:
    version = check["version"]
    if check.get("schema_version") != 1 or not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError("Invalid catalog check response")
    if check.get("sha256") != version[7:]:
        raise ValueError("Inconsistent catalog hash")
    interval = check.get("check_interval_seconds", 21600)
    if type(interval) is not int or interval <= 0:
        raise ValueError("Invalid check interval")
    return version, interval
