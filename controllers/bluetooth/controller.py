"""Compose Bluetooth link, device commands and the single receive path."""

import threading
from typing import Callable, Optional

from utils.app.i18n import message as m

from ..battery.polling import BatteryPolling
from ..equalizer.transport import EqTransport
from ..gestures.transport import GestureTransport
from ..latency.transport import LatencyTransport
from ..noise.protocol import noise_backend_enabled
from ..noise.transport import NoiseTransport
from .auth.auth_session import AuthPolicy
from .commands import DeviceCommands
from .identity import IdentitySession
from .link.session import BluetoothSession
from .packets.dispatch import PacketDispatcher
from .packets.protocol import BudsProtocol
from .packets.rcsp import DeviceIdentity


StatusCallback = Callable[[str, str], None]
BatteryCallback = Callable[[int, int, int], None]
CheckBatteryCallback = Callable[[], None]
ConnectionEventCallback = Callable[[str], None]


class BTController(BluetoothSession):
    """Provide the app's Bluetooth API and coordinate its device-specific components."""

    def __init__(
        self,
        status_callback: Optional[StatusCallback] = None,
        battery_callback: Optional[BatteryCallback] = None,
        check_battery_callback: Optional[CheckBatteryCallback] = None,
        connection_event_callback: Optional[ConnectionEventCallback] = None,
        bd_addr: Optional[str] = None,
        identity_callback: Optional[Callable[[DeviceIdentity], None]] = None,
        connection_state_callback: Optional[Callable[[str, str], None]] = None,
        auth_policy: AuthPolicy | str | None = None,
        error_callback: Optional[Callable] = None,
    ):
        super().__init__(
            bd_addr=bd_addr, auth_policy=auth_policy, status_callback=status_callback,
            connection_event_callback=connection_event_callback,
            connection_state_callback=connection_state_callback, error_callback=error_callback,
        )
        self._protocol = BudsProtocol()
        self._identity = IdentitySession(identity_callback)
        self._gestures = GestureTransport(self.connection)
        self._equalizer = EqTransport(self._gestures)
        self._latency = LatencyTransport(self._gestures)
        self._noise = NoiseTransport(self._gestures)
        self._rx_lock = threading.RLock()
        self._battery_callback = battery_callback
        self._check_battery_callback = check_battery_callback
        self.config_callback = None
        self.noise_callback = None
        self._battery = BatteryPolling(lock=self._state_lock, notify=self._notify_battery)
        self._commands = DeviceCommands(
            link=self, protocol=self._protocol, identity=self._identity, battery=self._battery,
            gestures=self._gestures, equalizer=self._equalizer, latency=self._latency, noise=self._noise,
        )
        self._dispatcher = PacketDispatcher(
            gestures=self._gestures, equalizer=self._equalizer, latency=self._latency, noise=self._noise,
            capture_noise=lambda: noise_backend_enabled(self.capabilities),
            on_identity=self._process_identity_packets, on_battery=self._battery.on_statuses,
            on_noise=self._notify_noise, on_config=self._notify_config,
        )

    @property
    def device_identity(self) -> Optional[DeviceIdentity]:
        return self._identity.current

    @property
    def diagnostic_identity(self) -> dict:
        return self._identity.diagnostics(self._bd_addr, self._device_name)

    @property
    def capabilities(self):
        return self._commands.capabilities

    @property
    def gesture_session(self):
        return self._gestures.generation

    @property
    def eq_session(self):
        return self._gestures.generation

    @property
    def eq_profiles(self):
        return self._commands.eq_profiles

    @property
    def noise_capabilities(self):
        return self._commands.noise_capabilities

    @property
    def gesture_capabilities(self):
        return self._commands.gesture_capabilities

    @property
    def latency_state(self):
        return self._commands.latency_state

    def send_command(self, mode: str = "low") -> tuple[bool, str]:
        return self._commands.send_command(mode)

    def send_raw(self, data: bytes) -> tuple[bool, str]:
        return self._commands.send_raw(data)

    def request_latency_state(self, *, session=None, timeout=5.0):
        return self._commands.request_latency_state(session=session, timeout=timeout)

    def set_battery_polling_active(self, active: bool) -> None:
        self._commands.set_battery_polling_active(active)

    def request_battery(self, user_initiated: bool = True) -> tuple[bool, str]:
        return self._commands.request_battery(user_initiated)

    def request_device_identity(self, timeout: float = 5.0, *, reconnect: bool = True) -> tuple[bool, str]:
        return self._commands.request_device_identity(timeout, reconnect=reconnect)

    def request_noise_settings(self, *, session, timeout=2.0):
        return self._commands.request_noise_settings(session=session, timeout=timeout)

    def set_adaptive_noise(self, enabled, *, session, timeout=2.0):
        return self._commands.set_adaptive_noise(enabled, session=session, timeout=timeout)

    def set_noise_settings(self, mode, level=None, *, session, timeout=2.0):
        return self._commands.set_noise_settings(mode, level, session=session, timeout=timeout)

    def request_eq_settings(self, timeout=5.0, *, session=None):
        return self._commands.request_eq_settings(timeout, session=session)

    def apply_eq(self, operation, *, profile=None, bands=(), timeout=5.0, session=None):
        return self._commands.apply_eq(operation, profile=profile, bands=bands, timeout=timeout, session=session)

    def request_gesture_settings(self, timeout=5.0, *, session=None):
        return self._commands.request_gesture_settings(timeout, session=session)

    def set_gesture_assignment(self, gesture_type, side, action, timeout=5.0, *, session=None):
        return self._commands.set_gesture_assignment(gesture_type, side, action, timeout, session=session)

    def on_connect_setup(self) -> None:
        self._commands.on_connect_setup(send_raw=self.send_raw, request_battery=self.request_battery)

    def _mark_received(self) -> None:
        self._battery.mark_received()

    def _check_connection_health(self) -> None:
        if self._running and self.connected and self.capabilities.supports("battery"):
            self._battery.check_health(self.request_battery)

    def _process_data(self, last_packet_size: int) -> int:
        """Process incoming data packet."""
        session = self.eq_session
        transport = self._connection.result
        try:
            data = self._connection.receive()
        except OSError:
            if session != self.eq_session or transport is not self._connection.result:
                return last_packet_size
            raise
        if session != self.eq_session or transport is not self._connection.result:
            return last_packet_size
        if not data:
            raise ConnectionError("Received zero bytes from RFCOMM socket")
        self._mark_received()

        packet_size = len(data)
        print(f"Received data size: {packet_size}")
        with self._rx_lock:
            if session != self.eq_session or not self.connected:
                return packet_size
            handled = self._dispatcher.feed(data, connection=self._connection, session=session)
            if not handled and self._protocol.is_mode_ack_packet(packet_size) and last_packet_size != packet_size:
                self._trigger_battery_check()

        return packet_size

    def _process_identity_packets(self, packets) -> None:
        self._identity.feed_packets(packets, address=self._bd_addr, device_name=self._device_name)

    def _notify_noise(self, session, state):
        if self.noise_callback:
            self.noise_callback(session, state)

    def _notify_config(self, session, records, eq):
        if self.config_callback:
            self.config_callback(session, records, eq)

    def _reset_session_state(self, reason: str) -> None:
        with self._rx_lock:
            self._battery.reset()
            self._dispatcher.reset()
            self._gestures.reset(m("gesture.connection_changed"))
            self._noise.reset()
            self._identity.reset(reason)

    def _trigger_battery_check(self) -> None:
        """Trigger battery check callback."""
        if self._check_battery_callback:
            self._check_battery_callback()

    def _notify_battery(self, left: int, right: int, case: int) -> None:
        """Notify UI of battery status."""
        if self._battery_callback:
            self._battery_callback(left, right, case)
