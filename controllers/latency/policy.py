"""Decide the desired latency mode from fullscreen activity and app rules."""

from dataclasses import dataclass

from utils.app.i18n import message as m


@dataclass(frozen=True)
class LatencyDecision:
    enabled: bool
    status: str
    activation_app: str = ""
    # None keeps the existing hold. An empty string clears it.
    hold_app: str | None = ""


def evaluate_policy(*, mode, is_fullscreen, app_id, includes, excludes,
                    hold_enabled, current_hold, is_process_running) -> LatencyDecision:
    if mode == "on":
        return LatencyDecision(True, m("latency.enabled"))
    if mode != "auto":
        return LatencyDecision(False, m("latency.standard_restored"))

    app_id = (app_id or "").strip().lower()
    included = bool(app_id and app_id in includes)
    excluded = bool(app_id and app_id in excludes)
    if included or (is_fullscreen and app_id and not excluded):
        status = m("latency.included" if included else "latency.fullscreen")
        return LatencyDecision(True, status, activation_app=app_id, hold_app=app_id if hold_enabled else "")
    if hold_enabled and current_hold and is_process_running(current_hold):
        return LatencyDecision(True, m("latency.keeping", app=current_hold),
                               activation_app=current_hold, hold_app=None)
    status = m("latency.skipped", app=app_id) if excluded else m("latency.fullscreen_ended")
    return LatencyDecision(False, status)
