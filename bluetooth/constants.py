"""Bluetooth Controller Constants."""

# ─────────────────────────────────────────────────────────────────────────────
# Connection Settings
# ─────────────────────────────────────────────────────────────────────────────
RFCOMM_PORT = 6
SOCKET_TIMEOUT = 2
RECONNECT_DELAY = 5
RECV_BUFFER_SIZE = 1024

# ─────────────────────────────────────────────────────────────────────────────
# Data Packet Sizes
# ─────────────────────────────────────────────────────────────────────────────
PACKET_SIZE_BATTERY_A = 62
PACKET_SIZE_BATTERY_B = 76
PACKET_SIZE_BATTERY_C = 164
PACKET_SIZE_MODE_ACK = 14

# ─────────────────────────────────────────────────────────────────────────────
# Protocol Patterns
# ─────────────────────────────────────────────────────────────────────────────
BATTERY_PATTERN = bytes.fromhex("02020407")
BATTERY_REQUEST_PAYLOAD = "fedcbac40200050bffffffffef4f"
MODE_COMMAND_TEMPLATE = "fedcbac4f20005{counter}03002f{param}ef"
COUNTER_VALUE = 0x90
