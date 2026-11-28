"""Maintain mutually exclusive include and exclude rules per platform."""

from utils.app.user_preferences import (
    get_all_low_latency_exceptions,
    get_all_low_latency_includes,
    set_low_latency_exceptions,
    set_low_latency_includes,
)


class LatencyRules:
    def __init__(self):
        self.exceptions_by_platform = get_all_low_latency_exceptions()
        self.includes_by_platform = get_all_low_latency_includes()

    def change(self, platform: str, value: str, mode: str):
        platform = (platform or "").strip().lower()
        app_id = (value or "").strip().lower()
        if platform not in {"windows", "linux"} or not app_id or mode not in {"exclude", "include", "remove"}:
            return None

        excluded = set(self.exceptions_by_platform.get(platform, []))
        included = set(self.includes_by_platform.get(platform, []))
        excluded.discard(app_id)
        included.discard(app_id)
        if mode == "exclude":
            excluded.add(app_id)
        elif mode == "include":
            included.add(app_id)

        excluded_sorted, included_sorted = sorted(excluded), sorted(included)
        self.exceptions_by_platform[platform] = excluded_sorted
        self.includes_by_platform[platform] = included_sorted
        set_low_latency_exceptions(excluded_sorted, platform=platform)
        set_low_latency_includes(included_sorted, platform=platform)
        return platform, app_id, excluded_sorted, included_sorted
