"""EQ transactions share the gesture channel's lock, counter and stream parser."""
from utils.i18n import message as m, error_message
from .equalizer import (
    EqResult, EqState, build_eq_request, build_profile, build_custom_eq,
    build_eq_reset, parse_profile, parse_custom_eq,
)


class EqTransport:
    def __init__(self, channel):
        self.channel = channel
        self._state = None
        self._session = None

    def _exchange(self, opcode, builder, config, timeout, session):
        return self.channel.exchange(opcode, builder, timeout, session, config)

    def read(self, timeout=5.0, session=None, *, custom=True):
        session = self.channel.generation if session is None else session
        with self.channel.transaction():
            include_custom = custom
            profile, custom, errors = None, None, []
            configs = ((7, parse_profile), (55, parse_custom_eq)) if include_custom else ((7, parse_profile),)
            for config, parser in configs:
                try:
                    data = self._exchange(0xF3, lambda ss: build_eq_request(ss, config), config, timeout, session)
                    value = parser(data)
                    if config == 7:
                        profile = value
                    else:
                        custom = value
                except (OSError, ValueError) as exc:
                    errors.append(error_message(exc))
            if session != self.channel.generation:
                return EqResult(False, message=m("eq.connection_changed"))
            state = EqState(profile, custom)
            self._state = state if profile is not None or custom is not None else None
            self._session = session
            if self._state is None:
                return EqResult(False, message=m("eq.failed", details="; ".join(errors)))
            return EqResult(True, state, m("eq.loaded") if custom or not include_custom else m("eq.presets_only"))

    def apply(self, operation, *, profile=None, bands=(), timeout=5.0, session=None):
        session = self.channel.generation if session is None else session
        with self.channel.transaction():
            try:
                if self._state is None or self._session != session or session != self.channel.generation:
                    raise ValueError(m("eq.refresh_first"))
                state, custom = self._state, self._state.custom
                if operation == "profile":
                    if state.profile is None:
                        raise ValueError(m("eq.refresh_first"))
                    config, builder = 7, lambda ss: build_profile(ss, profile)
                else:
                    if custom is None:
                        raise ValueError(m("eq.unsupported"))
                    config = 55
                    if operation in ("preview", "save"):
                        if tuple(b.frequency for b in bands) != tuple(b.frequency for b in custom.bands):
                            raise ValueError(m("eq.invalid"))
                        builder = lambda ss: build_custom_eq(ss, bands, custom.bound, preview=operation == "preview")
                    elif operation == "reset":
                        builder = build_eq_reset
                    else:
                        raise ValueError(m("eq.invalid"))
                self._exchange(0xF2, builder, config, timeout, session)
                if operation == "preview":
                    return EqResult(True, state, m("eq.previewed"))
                parser = parse_profile if config == 7 else parse_custom_eq
                actual = parser(self._exchange(0xF3, lambda ss: build_eq_request(ss, config), config, timeout, session))
                if operation == "profile":
                    confirmed = actual == profile
                    state = EqState(actual, custom)
                else:
                    expected = tuple(bands) if operation == "save" else tuple(
                        type(b)(b.frequency, 0) for b in custom.bands)
                    confirmed = (actual.bands == expected and (operation != "save" or actual.mode == 10))
                    state = EqState(state.profile, actual)
                if not confirmed:
                    raise ValueError(m("eq.unconfirmed"))
                # Keep 0007 independently authoritative after 0037 changes.
                if config == 55:
                    try:
                        current = parse_profile(self._exchange(0xF3, lambda ss: build_eq_request(ss, 7), 7, timeout, session))
                    except (OSError, ValueError):
                        current = None
                    state = EqState(current, state.custom)
                if session != self.channel.generation:
                    raise ConnectionError(m("eq.connection_changed"))
                self._state = state
                return EqResult(True, state, m("eq.saved" if operation != "reset" else "eq.reset_done"))
            except (OSError, ValueError) as exc:
                self._state = None
                return EqResult(False, message=m("eq.failed", details=error_message(exc)))
