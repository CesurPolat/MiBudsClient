"""Bounded SDP lookup through Windows Winsock or Linux BlueZ (no BT packages).

The PowerShell child isolates blocking native SDP calls so cancellation kills
and reaps the actual query, including WSALookupServiceBegin. Works when frozen.
"""
import base64
import re
import socket
import subprocess
import sys
import time
from uuid import UUID
import xml.etree.ElementTree as ET


class ConnectionCancelled(OSError):
    pass


SERVICE_UUIDS = (
    "0000fd2d-0000-1000-8000-00805f9b34fb",
    "00001101-0000-1000-8000-008584d01810",
    "00001101-0000-1000-8000-00805f9b34fb",
)

# WSAQUERYSETW uses native pointer alignment; SOCKADDR_BTH uses pack(1).
_WINDOWS_QUERY = r'''
$ErrorActionPreference = 'Stop'
try {
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MiBudsSdp {
 [StructLayout(LayoutKind.Sequential, Pack=1)]
 struct Bth { public ushort family; public ulong address; public Guid service; public uint port; }
 [StructLayout(LayoutKind.Sequential)]
 struct Addr { public IntPtr ptr; public int length; }
 [StructLayout(LayoutKind.Sequential)]
 struct Cs { public Addr local; public Addr remote; public int type; public int protocol; }
 [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
 struct Query {
  public uint size; public IntPtr name; public IntPtr service; public IntPtr version;
  public IntPtr comment; public uint ns; public IntPtr provider;
  [MarshalAs(UnmanagedType.LPWStr)] public string context;
  public uint protocols; public IntPtr protocolList; public IntPtr query;
  public uint addresses; public IntPtr addressList; public uint flags; public IntPtr blob;
 }
 [DllImport("ws2_32.dll")] static extern int WSAStartup(ushort v, IntPtr data);
 [DllImport("ws2_32.dll")] static extern int WSACleanup();
 [DllImport("ws2_32.dll")] static extern int WSAGetLastError();
 [DllImport("ws2_32.dll", CharSet=CharSet.Unicode)] static extern int WSAAddressToStringW(ref Bth a, uint n, IntPtr info, System.Text.StringBuilder s, ref uint len);
 [DllImport("ws2_32.dll", CharSet=CharSet.Unicode)] static extern int WSALookupServiceBeginW(ref Query q, uint flags, out IntPtr handle);
 [DllImport("ws2_32.dll", CharSet=CharSet.Unicode)] static extern int WSALookupServiceNextW(IntPtr handle, uint flags, ref uint size, IntPtr result);
 [DllImport("ws2_32.dll")] static extern int WSALookupServiceEnd(IntPtr handle);
 static Exception Error() { return new System.ComponentModel.Win32Exception(WSAGetLastError()); }
 public static int Resolve(string mac, string uuid) {
  IntPtr data=Marshal.AllocHGlobal(512), guid=Marshal.AllocHGlobal(16), handle=IntPtr.Zero;
  bool started=false;
  try {
   int err=WSAStartup(0x202,data); if(err!=0) throw new System.ComponentModel.Win32Exception(err); started=true;
   ulong address=Convert.ToUInt64(mac.Replace(":",""),16);
   Bth peer=new Bth { family=32, address=address };
   var context=new System.Text.StringBuilder(128); uint length=128;
   if(WSAAddressToStringW(ref peer,(uint)Marshal.SizeOf(typeof(Bth)),IntPtr.Zero,context,ref length)!=0) throw Error();
   Marshal.StructureToPtr(new Guid(uuid),guid,false);
   Query query=new Query { size=(uint)Marshal.SizeOf(typeof(Query)), service=guid, ns=16, context=context.ToString() };
   if(WSALookupServiceBeginW(ref query,0x1000,out handle)!=0) {
    int code=WSAGetLastError(); if(code==10108 || code==10110 || code==10102) return 0; throw new System.ComponentModel.Win32Exception(code);
   }
   uint capacity=4096;
   while(true) {
    IntPtr buffer=Marshal.AllocHGlobal((int)capacity);
    try {
     Marshal.WriteInt32(buffer,Marshal.SizeOf(typeof(Query)));
     uint size=capacity;
     if(WSALookupServiceNextW(handle,0x100,ref size,buffer)!=0) {
      int code=WSAGetLastError();
      if(code==10014 && size>capacity && size<=1048576) { capacity=size; continue; }
      if(code==10110 || code==10102 || code==10108) return 0;
      throw new System.ComponentModel.Win32Exception(code);
     }
     Query result=(Query)Marshal.PtrToStructure(buffer,typeof(Query));
     for(int i=0;i<result.addresses;i++) {
      Cs cs=(Cs)Marshal.PtrToStructure(IntPtr.Add(result.addressList,i*Marshal.SizeOf(typeof(Cs))),typeof(Cs));
      // Windows providers may report the endpoint in LocalAddr or RemoteAddr.
      foreach(Addr a in new Addr[] {cs.remote,cs.local}) {
       if(a.ptr==IntPtr.Zero || a.length<Marshal.SizeOf(typeof(Bth))) continue;
       Bth endpoint=(Bth)Marshal.PtrToStructure(a.ptr,typeof(Bth));
       if(endpoint.family==32 && endpoint.address==address && endpoint.port>=1 && endpoint.port<=30 && cs.protocol==3) return (int)endpoint.port;
      }
     }
    } finally { Marshal.FreeHGlobal(buffer); }
   }
  } finally {
   if(handle!=IntPtr.Zero) WSALookupServiceEnd(handle);
   if(started) WSACleanup(); Marshal.FreeHGlobal(guid); Marshal.FreeHGlobal(data);
  }
 }
}
'@
[MiBudsSdp]::Resolve('__ADDRESS__', '__UUID__')
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
'''


class PlatformBackend:
    @property
    def resolution_source(self):
        return "linux_sdp" if sys.platform.startswith("linux") else "windows_sdp"

    def resolve_rfcomm_channel(self, address, service_uuid, timeout, cancel):
        if sys.platform != "win32" and not sys.platform.startswith("linux"):
            return None
        if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", address):
            raise ValueError("Invalid Bluetooth address")
        service_uuid = str(UUID(service_uuid))
        if sys.platform.startswith("linux"):
            return self._resolve_linux_channel(address, service_uuid, timeout, cancel)
        deadline = time.monotonic() + timeout
        script = _WINDOWS_QUERY.replace("__ADDRESS__", address).replace("__UUID__", service_uuid)
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        with subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000,
        ) as process:
            try:
                while True:
                    if cancel.is_set():
                        raise ConnectionCancelled("SDP lookup cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("SDP lookup timed out")
                    try:
                        output, error = process.communicate(timeout=min(0.05, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
                if process.returncode:
                    raise OSError("Windows SDP query failed: " + error.decode(errors="replace").strip())
                channel = int(output.strip())
                if channel == 0:
                    return None
                if not 1 <= channel <= 30:
                    raise OSError("Invalid SDP RFCOMM channel")
                return channel
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def _resolve_linux_channel(self, address, service_uuid, timeout, cancel):
        deadline = time.monotonic() + timeout
        if cancel.is_set():
            raise ConnectionCancelled("SDP lookup cancelled")
        if timeout <= 0:
            raise TimeoutError("SDP lookup timed out")
        # Search Bluetooth-base UUIDs directly, including services that are not
        # in the public browse group. sdptool search cannot accept an arbitrary
        # vendor 128-bit UUID, so browse this peer for those and match locally.
        # No RFCOMM channels are probed and no other Bluetooth peers are scanned.
        if service_uuid[8:] == "-0000-1000-8000-00805f9b34fb":
            command = ["sdptool", "search", "--bdaddr", address, "--xml",
                       f"0x{int(service_uuid[:8], 16):x}"]
        else:
            command = ["sdptool", "browse", "--xml", address]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError as error:
            raise OSError("Linux SDP discovery requires BlueZ's sdptool") from error
        with process:
            try:
                while True:
                    if cancel.is_set():
                        raise ConnectionCancelled("SDP lookup cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Linux SDP lookup timed out")
                    try:
                        output, error = process.communicate(timeout=min(0.05, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
                if cancel.is_set():
                    raise ConnectionCancelled("SDP lookup cancelled")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Linux SDP lookup timed out")
                if process.returncode:
                    raise OSError("Linux SDP query failed: " + error.decode(errors="replace").strip())
                # Some sdptool versions report failed browse requests on stderr
                # while returning zero. Do not present those as empty catalogs.
                if error.strip():
                    raise OSError("Linux SDP query reported: " + error.decode(errors="replace").strip())
                return _linux_record_channel(output, service_uuid)
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def create_rfcomm_socket(self):
        return socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)


def _sdp_uuid(value):
    """Expand only standard short UUIDs; preserve vendor-specific 128-bit IDs."""
    if re.fullmatch(r"(?:0x)?[0-9a-fA-F]{1,8}", value):
        short = int(value, 16)
        return str(UUID(f"{short:08x}-0000-1000-8000-00805f9b34fb"))
    return str(UUID(value))


def _linux_record_channel(output, service_uuid):
    """Read RFCOMM only from the exact service's own ProtocolDescriptorList."""
    # BlueZ emits separate XML documents, with optional human-readable headers.
    # Parse each record independently, so channels cannot cross record bounds.
    records = re.findall(rb"<record\b[^>]*>.*?</record\s*>", output, re.DOTALL)
    if output.count(b"<record") != len(records):
        raise OSError("Incomplete Linux SDP XML records")
    channels = set()
    for raw in records:
        try:
            record = ET.fromstring(raw)
            attributes = {int(attr.attrib["id"], 0): attr for attr in record.findall("attribute")}
            services = []
            for attribute_id in (0x0001, 0x0003):  # ServiceClassIDList, ServiceID
                attr = attributes.get(attribute_id)
                if attr is not None:
                    services.extend(_sdp_uuid(node.attrib["value"]) for node in attr.iter("uuid"))
            if service_uuid not in services:
                continue
            protocols = attributes.get(0x0004)
            if protocols is None:
                continue
            for descriptor in protocols.findall("./sequence/sequence"):
                fields = list(descriptor)
                if not fields or fields[0].tag != "uuid":
                    continue
                if _sdp_uuid(fields[0].attrib["value"]) != "00000003-0000-1000-8000-00805f9b34fb":
                    continue
                if len(fields) != 2 or fields[1].tag != "uint8":
                    raise ValueError("Invalid RFCOMM descriptor")
                channel = int(fields[1].attrib["value"], 0)
                if not 1 <= channel <= 30:
                    raise ValueError("Invalid RFCOMM channel")
                channels.add(channel)
        except (ET.ParseError, KeyError, ValueError) as error:
            raise OSError("Invalid Linux SDP service record") from error
    if len(channels) > 1:
        raise OSError("Ambiguous RFCOMM channels for the requested service UUID")
    return next(iter(channels), None)
