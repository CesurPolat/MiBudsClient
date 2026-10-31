"""Bounded Windows SDP lookup, using the OS Winsock provider (no BT packages).

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
    def resolve_rfcomm_channel(self, address, service_uuid, timeout, cancel):
        if sys.platform != "win32":
            # Preserve Linux's validated profile path; no speculative SDP tool dependency.
            return None
        if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", address):
            raise ValueError("Invalid Bluetooth address")
        service_uuid = str(UUID(service_uuid))
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

    def create_rfcomm_socket(self):
        return socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
