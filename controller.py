import socket
import time
import threading
import subprocess
import json
import sys

BD_ADDR = None
PORT = 6

class BTController:
    def __init__(self, status_callback=None, battery_callback=None, check_battery_callback=None):
        self.sock = None
        self.running = True
        self.connected = False
        self.lock = threading.Lock()
        self.bd_addr = BD_ADDR
        self.status_callback = status_callback
        self.battery_callback = battery_callback
        self.check_battery_callback = check_battery_callback
        
    def _update_status(self, text, color="black"):
        if self.status_callback:
            self.status_callback(text, color)

    def connect(self):
        if not self.bd_addr:
            device = self.get_connected_bluetooth_device()
            if device and device.get("address"):
                self.bd_addr = device["address"]
                self._update_status(f"MAC found: {self.bd_addr}", "blue")
            else:
                self._update_status("No connected Bluetooth device found", "red")
                return False

        try:
            self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.settimeout(2)
            self.sock.connect((self.bd_addr, PORT))
            self.connected = True
            self._update_status("Connected", "blue")
            
            if self.check_battery_callback:
                # We use a small delay usually handled by UI thread, 
                # but here we can just signal the UI to request it or do it after a bit.
                # For now, let's just trigger the callback.
                self.check_battery_callback()
            return True
        except Exception as e:
            self.connected = False
            self._update_status(f"Connection failed: {e}", "red")
            return False

    def listen(self):
        last_len = 0
        while self.running:
            if not self.connected:
                self.connect()
                time.sleep(5)
                continue
            
            try:
                data = self.sock.recv(1024)
                dlen = len(data)
                print(f"Received data size: {dlen}")
                
                if dlen == 62 or dlen == 76:
                    self.parse_battery(data)
                elif dlen == 14:
                    if last_len != 14:
                        if self.check_battery_callback:
                            self.check_battery_callback()
                
                last_len = dlen
            except socket.timeout:
                continue
            except Exception as e:
                self.connected = False
                self._update_status("Connection lost", "red")
                time.sleep(2)

    def send_command(self, mode="low"):
        if not self.connected:
            if not self.connect():
                return False, "Could not connect to device."
        
        param = "01" if mode == "low" else "00"
        counter_int = 0x90 
        current_counter = hex(counter_int)[2:].zfill(2)
        payload = f"fedcbac4f20005{current_counter}03002f{param}ef"
        
        try:
            with self.lock:
                self.sock.send(bytes.fromhex(payload))
            return True, f"{'Low latency' if mode == 'low' else 'Standard'} mode sent."
        except Exception as e:
            self.connected = False
            return False, f"Send error: {e}"

    def request_battery(self):
        if not self.connected:
            if not self.connect():
                return False, "Could not connect to device."
        
        # User provided battery check payload
        payload = "fedcbac40200050bffffffffef4f"
        
        try:
            with self.lock:
                self.sock.send(bytes.fromhex(payload))
            return True, "Battery request sent."
        except Exception as e:
            self.connected = False
            return False, f"Request error: {e}"

    def parse_battery(self, data):
        try:
            # Pattern: 02 02 04 07 [L] [R] [C]
            pattern = bytes.fromhex("02020407")
            idx = data.find(pattern)
            
            if idx != -1 and len(data) >= idx + 7:
                left = data[idx + 4]
                right = data[idx + 5]
                case = data[idx + 6]
                
                if self.battery_callback:
                    self.battery_callback(left, right, case)
        except Exception:
            pass

    # TODO: Add support for Linux/Mac if needed, currently only Windows is supported for auto MAC detection
    def get_connected_bluetooth_device(self):
        if sys.platform != "win32":
            return None

        def format_mac(addr: str) -> str:
            if not addr:
                return addr
            cleaned = addr.replace(":", "").replace("-", "").replace(" ", "").upper()
            if len(cleaned) == 12:
                return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
            return addr

        ps_script = r"""
$bt = Get-PnpDevice -Class Bluetooth -Status OK
$results = foreach ($d in $bt) {
    $isConn = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_IsConnected' -ErrorAction SilentlyContinue).Data
    if ($isConn -eq $true) {
        $addr = (Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Bluetooth_DeviceAddress' -ErrorAction SilentlyContinue).Data
        if ($addr -is [byte[]]) {
            $addrStr = ($addr | ForEach-Object { $_.ToString('X2') }) -join ':'
        } else {
            $addrStr = [string]$addr
        }
        [pscustomobject]@{ Name=$d.FriendlyName; Address=$addrStr }
    }
}
if ($results) { $results | ConvertTo-Json -Compress }
"""

        try:
            output = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_script],
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            ).strip()
            if not output:
                return None
            data = json.loads(output)
            if isinstance(data, list):
                for item in data:
                    address = item.get("Address")
                    if address:
                        return {"name": item.get("Name"), "address": format_mac(address)}
                return None
            return {"name": data.get("Name"), "address": format_mac(data.get("Address"))}
        except Exception:
            return None

    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
