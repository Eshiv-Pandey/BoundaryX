"""Owned native TCP transport for unchanged AP2 applications and SDK handlers.

No ASGITransport forwards an application request. Uvicorn serves each exact
observed original app on an owned loopback socket; HTTPX uses real TCP. Socket
allocation, runtime observation and strict cleanup are disclosed interventions.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import httpx


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def append(path, value):
    with Path(path).open("ab") as handle:
        handle.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


class BridgeInitiationBoundary(RuntimeError):
    """An actual public MCP reply was retained; no inverse Task was fabricated."""


class OwnedPeerGroup:
    def __init__(self, output, writer, bridge_initiation=None):
        self.output, self.write, self.bridge_initiation = Path(output), writer, bridge_initiation
        self.peers = {}
        self.lock = asyncio.Lock()
        self.started = False
        self.closed = False
        self.cleanup_complete = False
        self.requests = []

    def allocate(self, role, app, port):
        if self.started or port in self.peers or role in {row["role"] for row in self.peers.values()}:
            raise ValueError("fresh_unique_native_peer_required")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.set_inheritable(False)
            listener.bind(("127.0.0.1", port))
            endpoint = listener.getsockname()
            if endpoint != ("127.0.0.1", port):
                raise ValueError("native_socket_endpoint_changed")
            descriptor = listener.fileno()
            stat = os.fstat(descriptor) if os.name != 'nt' else None
            row = {"role": role, "app": app, "socket": listener, "server": None, "task": None,
                   "allocation": {"schema_version": "ap2-owned-native-socket/10", "role": role,
                                  "process_id": os.getpid(), "allocated_utc": now(), "host": endpoint[0],
                                  "port": endpoint[1], "descriptor": descriptor,
                                  "socket_device": stat.st_dev if stat is not None else None,
                                  "socket_inode": stat.st_ino if stat is not None else None,
                                  "socket_identity_source": "POSIX fstat" if stat is not None else "Winsock descriptor; no inode claim",
                                  "inheritable": listener.get_inheritable(), "original_card_rewritten": False,
                                  "bootstrap": "owned_Uvicorn_over_exact_original_observed_application"}}
            self.peers[port] = row
            self.write(self.output / (role + "-socket-allocation.json"), row["allocation"])
            return OwnedTcpTransport(self, port)
        except BaseException:
            listener.close()
            raise

    async def start(self):
        async with self.lock:
            if self.started:
                return
            if not self.peers or self.closed:
                raise ValueError("owned_native_peers_not_allocated")
            import uvicorn
            for port, row in self.peers.items():
                config = uvicorn.Config(row["app"], host="127.0.0.1", port=port,
                                        loop="asyncio", http="h11", ws="none", lifespan="off", log_config=None,
                                        access_log=False, log_level="warning", timeout_keep_alive=1,
                                        timeout_graceful_shutdown=3)
                row["server"] = uvicorn.Server(config)
                row["task"] = asyncio.create_task(row["server"].serve(sockets=[row["socket"]]))
            deadline = time.monotonic() + 10
            while not all(row["server"].started for row in self.peers.values()):
                for row in self.peers.values():
                    if row["task"].done():
                        row["task"].result()
                        raise ValueError("owned_native_server_ended_before_start")
                if time.monotonic() >= deadline:
                    raise TimeoutError("owned_native_server_startup_bound")
                await asyncio.sleep(0.01)
            self.started = True
            self.write(self.output / "native-servers-started.json", {
                "schema_version": "ap2-owned-native-sockets/10", "process_id": os.getpid(), "started_utc": now(),
                "uvicorn_version": uvicorn.__version__, "actual_tcp_listeners_started": True,
                "peers": [row["allocation"] for row in self.peers.values()],
                "in_process_asgi_transport_used": False, "provider_requests": 0,
            })

    async def handle(self, transport, request):
        await self.start()
        if self.closed or request.url.scheme != "http" or request.url.host not in {"localhost", "127.0.0.1"}:
            raise PermissionError("only_owned_peer_loopback_http_permitted")
        if request.url.port != transport.port or request.url.port not in self.peers:
            raise PermissionError("native_request_not_owned_peer_socket")
        if "authorization" in request.headers or "x-goog-api-key" in request.headers:
            raise PermissionError("native_credential_transport_header_refused")
        raw = request.content
        bridge_boundary = False
        if self.bridge_initiation is not None and transport.port == 8001 and request.method == 'POST':
            packet = json.loads(raw)
            message = packet.get('params', {}).get('message', {})
            text = [part.get('text') for part in message.get('parts', []) if part.get('kind') == 'text']
            bridge_boundary = text == ['Initiate a payment'] and not message.get('taskId')
        row = {"index": len(self.requests), "role": self.peers[transport.port]["role"],
               "method": request.method, "url": str(request.url), "request_entity": identity(raw),
               'request_path': request.url.path, 'request_raw_path': request.url.raw_path.split(b'?')[0].decode('ascii'),
               'request_query': request.url.query.decode('ascii'), 'request_headers': [list(row) for row in request.headers.multi_items()],
               "transport": "owned_httpx_AsyncHTTPTransport_over_actual_TCP",
               "attempted_utc": now(), "original_request_mutated_by_native_transport": False,
               "provider_request": False, "native_tcp_application_dispatch_attempted": not bridge_boundary,
               "owned_bridge_initiation_intercepted_before_native_dispatch": bridge_boundary}
        if len(self.requests) >= 128:
            raise ValueError("native_peer_total_request_bound")
        self.requests.append(row)
        append(self.output / "native-wire-attempts.jsonl", row)
        if bridge_boundary:
            await self.bridge_initiation(request)
            raise BridgeInitiationBoundary("actual_bridge_reply_retained_without_fabricated_inverse")
        response = await transport.network.handle_async_request(request)
        append(self.output / "native-wire-responses.jsonl", {
            "request_index": row["index"], "status_code": response.status_code, "returned_utc": now(),
            "role": row["role"], "url": row["url"], "transport": row["transport"],
        })
        return response

    async def close(self):
        if self.closed:
            return self.cleanup_complete
        self.closed = True
        rows = []
        for port, peer in reversed(list(self.peers.items())):
            error = None
            server, task = peer["server"], peer["task"]
            if server is not None:
                server.should_exit = True
            if task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=6)
                except BaseException as caught:
                    error = type(caught).__name__ + ": " + str(caught)[:500]
                    if server is not None:
                        server.force_exit = True
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass
            peer["socket"].close()
            endpoint_rebind_verified = False
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", port))
                endpoint_rebind_verified = probe.getsockname() == ("127.0.0.1", port)
            except OSError as caught:
                error = error or type(caught).__name__ + ": " + str(caught)[:500]
            finally:
                probe.close()
            rows.append({"role": peer["role"], "port": port, "process_id": os.getpid(),
                         "closed_utc": now(), "socket_closed": peer["socket"].fileno() == -1,
                         "server_task_finished": task is None or task.done(),
                         "endpoint_rebind_verified": endpoint_rebind_verified, "error": error})
        self.cleanup_complete = all(row["socket_closed"] and row["server_task_finished"]
                                    and row["endpoint_rebind_verified"] and row["error"] is None for row in rows)
        self.write(self.output / "native-socket-cleanup.json", {
            "schema_version": "ap2-owned-native-sockets/10", "strict_cleanup_passed": self.cleanup_complete,
            "peers": rows, "closed_utc": now(), "provider_requests": 0,
        })
        return self.cleanup_complete


class OwnedTcpTransport(httpx.AsyncBaseTransport):
    def __init__(self, group, port):
        self.group, self.port = group, port
        self.network = httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        return await self.group.handle(self, request)

    async def aclose(self):
        await self.network.aclose()
