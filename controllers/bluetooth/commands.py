"""Device commands and the capability checks shared by their callers."""

import time

from utils.app.i18n import error_message, message as m

from ..catalog.capabilities import DeviceCapabilities, resolve_capabilities
from ..equalizer.protocol import EqResult, eq_profiles
from ..gestures.protocol import GestureResult, gesture_capabilities, gesture_config
from ..noise.protocol import noise_backend_enabled, noise_capabilities


class DeviceCommands:
    def __init__(self, *, link, protocol, identity, battery, gestures, equalizer, latency, noise):
        self._link = link
        self._protocol = protocol
        self._identity = identity
        self._battery = battery
        self._gestures = gestures
        self._equalizer = equalizer
        self._latency = latency
        self._noise = noise

    def send_command(self, mode: str = "low") -> tuple[bool, str]:
        """Send latency mode command.

        Args:
            mode: "low" for low latency, "std" for standard

        Returns:
            (success, message) tuple
        """
        if not self._link._ensure_connected():
            return False, m("connection.device_failed")

        try:
            if not self.capabilities.supports("latency"):
                return False, m("connection.device_failed")
            if not self._link.session_ready:
                return False, m("latency.disconnected")
            self._latency.write(mode == "low")
            return True, m("command.mode_sent", mode=m("mode.low" if mode == "low" else "mode.standard"))
        except Exception as e:
            return False, m("latency.failed", details=error_message(e))

    @property
    def latency_state(self):
        return self._latency.state if self._link.session_ready else None

    def request_latency_state(self, *, session=None, timeout=5.0):
        """Read off the listener/UI thread, without reconnecting implicitly."""
        if not self._link.session_ready or not self.capabilities.supports("latency"):
            raise ConnectionError(m("latency.disconnected"))
        return self._latency.read(timeout, session)

    def set_battery_polling_active(self, active: bool) -> None:
        self._battery.set_active(active)

    def request_battery(self, user_initiated: bool = True) -> tuple[bool, str]:
        """Request battery status from device."""
        # User-invoked battery refresh should reopen reconnect attempts.
        if user_initiated:
            self._link.resume_reconnect_attempts()
        elif not self._battery.enabled:
            return False, m("connection.waiting")

        if not self._link._ensure_connected():
            return False, m("connection.device_failed")

        try:
            if not self.capabilities.supports("battery"):
                return False, m("connection.device_failed")
            payload = self._protocol.build_battery_request(self._identity.next_counter())
            if not self._battery.send_request(self._link.connection.send, payload, user_initiated=user_initiated):
                return False, m("connection.waiting")
            return True, m("battery.sent")
        except Exception as e:
            self._link.connection.connected = False
            return False, m("command.request_error", details=str(e))

    def request_device_identity(self, timeout: float = 5.0, *, reconnect: bool = True) -> tuple[bool, str]:
        """Read all target info and return raw hex; run off the UI/listener thread."""
        if timeout <= 0:
            raise ValueError("Identity timeout must be positive")
        if reconnect:
            self._link.resume_reconnect_attempts()
        if not (self._link._ensure_connected() if reconnect else self._link.connected):
            return False, m("connection.device_failed")

        return self._identity.request(self._link.connection, timeout)

    @property
    def capabilities(self):
        return resolve_capabilities(self._link.device_name, self._identity.current) if self._link.connected else DeviceCapabilities()

    @property
    def eq_profiles(self):
        return eq_profiles(self._link.device_name, self._identity.current)

    @property
    def noise_capabilities(self):
        return noise_capabilities(self.capabilities)

    def _require_noise_backend(self):
        if not self._link.session_ready or not noise_backend_enabled(self.capabilities):
            raise ValueError("Device session is not ready or catalog has no ANC/transparency feature")

    def request_noise_settings(self, *, session, timeout=2.0):
        self._require_noise_backend()
        self._noise.read_aux(self.noise_capabilities, session)
        return self._noise.read(session, timeout)

    def set_adaptive_noise(self, enabled, *, session, timeout=2.0):
        self._require_noise_backend()
        return self._noise.set_adaptive(self.noise_capabilities, session, enabled, timeout)

    def set_noise_settings(self, mode, level=None, *, session, timeout=2.0):
        self._require_noise_backend()
        return self._noise.apply(self.noise_capabilities, session, mode, level, timeout)

    def request_eq_settings(self, timeout=5.0, *, session=None):
        if not self.capabilities.supports("eq"):
            return EqResult(False, message=m("eq.unsupported"))
        return self._equalizer.read(timeout, session, custom=self.capabilities.supports("custom_eq"))

    def apply_eq(self, operation, *, profile=None, bands=(), timeout=5.0, session=None):
        if operation != "profile" and not self.capabilities.supports("custom_eq"):
            return EqResult(False, message=m("eq.unsupported"))
        if not self.capabilities.supports("eq") or (operation == "profile" and (type(profile) is not int or profile not in self.eq_profiles)):
            return EqResult(False, message=m("eq.unsupported"))
        return self._equalizer.apply(operation, profile=profile, bands=bands, timeout=timeout, session=session)

    @property
    def gesture_capabilities(self):
        return gesture_capabilities(self._link.device_name, self._identity.current)

    def request_gesture_settings(self, timeout=5.0, *, session=None):
        """Read off the UI/listener thread; never reconnect for a stale action."""
        if not self._link.connected:
            return GestureResult(False, message=m("gesture.connect"))
        if not self.gesture_capabilities:
            return GestureResult(False, message=m("gesture.no_capabilities"))
        configs = tuple(dict.fromkeys(gesture_config(g) for g in self.gesture_capabilities))
        return self._gestures.read(timeout, session, configs)

    def set_gesture_assignment(self, gesture_type, side, action, timeout=5.0, *, session=None):
        """Write one side, then verify by reading the device's settings back."""
        allowed = self.gesture_capabilities.get(gesture_type, ())
        if side not in ("left", "right", "common") or type(action) is not int or action not in allowed:
            return GestureResult(False, message=m("gesture.unsupported"))
        return self._gestures.write(gesture_type, side, action, timeout, session)

    def send_raw(self, data: bytes) -> tuple[bool, str]:
        """Send raw bytes to device.

        Args:
            data: Raw bytes to send

        Returns:
            (success, message) tuple
        """
        if not self._link._ensure_connected():
            return False, m("connection.device_failed")

        try:
            self._link.connection.send(data)
            return True, m("command.raw_sent", data=data.hex())
        except Exception as e:
            self._link.connection.connected = False
            return False, m("command.send_error", details=str(e))

    def on_connect_setup(self, *, send_raw, request_battery) -> None:
        """Initialize battery requests on the newly connected device."""
        if not self.capabilities.supports("battery"):
            return
        legacy_setup = (not self._link.connection.session_authenticated and
                        " ".join(self._link.device_name.split()).casefold() == "redmi buds 6 play")
        if legacy_setup:
            print(send_raw(bytes.fromhex("fedcba04510003000301ef")))
            time.sleep(0.1)
        time.sleep(1)
        request_battery(user_initiated=False)
