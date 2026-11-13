"""Read-only accepted IPv4 TCP socket ownership for a task-owned Windows Job.

The check runs after connect and before request bytes; it never finds a process
to signal or reads credentials. PID membership is observed, not authenticated.
"""
from datetime import datetime, timezone
import ctypes
import os
import socket
import struct
import time


def decode_table(raw):
    if type(raw) is not bytes or len(raw) < 4 or len(raw) > 1024 * 1024:
        raise ValueError("invalid bounded TCP owner table")
    count = struct.unpack_from("<I", raw)[0]
    if count > 4096 or len(raw) < 4 + count * 24:
        raise ValueError("TCP owner table count exceeds retained bytes or limit")
    rows = []
    for index in range(count):
        state, local, local_port, remote, remote_port, pid = struct.unpack_from("<6I", raw, 4 + index * 24)
        rows.append({"state": state, "local_address": socket.inet_ntoa(struct.pack("<I", local)),
                     "local_port": socket.ntohs(local_port & 0xFFFF),
                     "remote_address": socket.inet_ntoa(struct.pack("<I", remote)),
                     "remote_port": socket.ntohs(remote_port & 0xFFFF), "owner_pid": pid})
    return rows


def owner_table():
    if os.name != "nt":
        raise ValueError("native Windows TCP ownership is required")
    api = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
                    ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    api.restype = ctypes.c_uint32
    size = ctypes.c_uint32()
    # AF_INET=2, TCP_TABLE_OWNER_PID_ALL=5; table includes accepted connections.
    code = api(None, ctypes.byref(size), False, 2, 5, 0)
    if code not in (0, 122):
        raise OSError("TCP owner table size observation failed")
    for _ in range(3):
        if not 4 <= size.value <= 1024 * 1024:
            raise ValueError("TCP owner table byte bound exceeded")
        buffer = ctypes.create_string_buffer(size.value)
        code = api(buffer, ctypes.byref(size), False, 2, 5, 0)
        if code == 0:
            return decode_table(buffer.raw[:size.value])
        if code != 122:
            raise OSError("TCP owner table observation failed")
    raise ValueError("TCP owner table kept changing size")


def verify_connection(sock, native_pid, job, *, table_reader=owner_table):
    if type(native_pid) is not int or native_pid <= 0:
        raise ValueError("constructed original native PID must be a positive integer")
    local, peer = sock.getsockname(), sock.getpeername()
    if (len(local) != 2 or len(peer) != 2 or local[0] != "127.0.0.1" or peer[0] != "127.0.0.1"
            or any(type(endpoint[1]) is not int or not 1024 <= endpoint[1] <= 65535 for endpoint in (local, peer))):
        raise ValueError("accepted socket is not the exact numeric IPv4 loopback connection")
    if job.poll() is not None:
        raise ValueError("owned wrapper exited before request dispatch")
    before = job.members()
    if native_pid not in before:
        raise ValueError("constructed native PID is absent from this owned Job")
    # Match SERVER side: local=client peer, remote=client local. A different
    # process winning the listener race cannot receive request content here.
    matches = [row for row in table_reader() if row["state"] == 5
               and (row["local_address"], row["local_port"]) == peer
               and (row["remote_address"], row["remote_port"]) == local]
    after = job.members()
    if (len(matches) != 1 or matches[0]["owner_pid"] != native_pid or native_pid not in after
            or job.poll() is not None):
        raise ValueError("accepted TCP connection is not uniquely owned by the original native PID in this Job")
    return {"schema_version": "windows-owned-tcp-connection/1", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(), "native_pid": native_pid, "client_local": list(local), "client_peer": list(peer),
            "accepted_server_row": matches[0], "job_members_before": before, "job_members_after": after,
            "checked_before_request_bytes": True, "source_authentication_proven": False}
