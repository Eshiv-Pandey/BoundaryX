"""Injected public ASGI observation; no server, SDK or evaluator imports.

This wrapper observes the final original application boundary. Hook placement,
native capture completeness and socket ownership remain separate contracts.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import math


SCOPE_FIELDS = (
    "type", "asgi", "http_version", "scheme", "method", "path", "raw_path",
    "query_string", "root_path", "headers", "client", "server",
)


def lossless(value):
    """Tagged byte/tuple encoding without consulting application inner state."""
    if type(value) is bytes:
        return {"encoding": "base64", "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
                "data": base64.b64encode(value).decode("ascii")}
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is tuple:
        return {"encoding": "tuple", "items": [lossless(item) for item in value]}
    if type(value) is list:
        return [lossless(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: lossless(item) for key, item in value.items()}
    raise TypeError("Unsupported public wire value")


class PassiveAsgiCapture:
    """Forward the identical scope/events and preserve original exceptions.

    A synchronous sink receives detached records. Observation errors are kept
    in memory and never replace an application's response or transport error.
    In-memory records alone are not a durable or authenticated native capture.
    """
    def __init__(self, app, sink=None):
        self.app, self.sink = app, sink
        self.records, self.errors = [], []
        self.capture_complete = True
        self._exchange = 0

    def _record(self, exchange, boundary, value=None, error=None):
        try:
            row = {"sequence": len(self.records), "exchange": exchange,
                   "boundary": boundary, "value": lossless(value)}
            if error is not None:
                row["error_type"] = type(error).__name__
            self.records.append(row)
            if self.sink is not None:
                self.sink(deepcopy(row))
        except BaseException as observation_error:
            self.capture_complete = False
            self.errors.append({"exchange": exchange, "boundary": boundary,
                                "error_type": type(observation_error).__name__})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        exchange = self._exchange
        self._exchange += 1
        self._record(exchange, "scope", {key: scope[key] for key in SCOPE_FIELDS if key in scope})

        async def observed_receive():
            self._record(exchange, "receive_attempt")
            try:
                event = await receive()
            except BaseException as error:
                self._record(exchange, "receive_error", error=error)
                raise
            self._record(exchange, "receive_returned", event)
            return event

        async def observed_send(event):
            self._record(exchange, "send_attempt", event)
            try:
                result = await send(event)
            except BaseException as error:
                self._record(exchange, "send_error", error=error)
                raise
            self._record(exchange, "send_completed", event)
            return result

        try:
            result = await self.app(scope, observed_receive, observed_send)
        except BaseException as error:
            self._record(exchange, "application_error", error=error)
            raise
        self._record(exchange, "application_returned")
        return result

    def report(self):
        return {"schema_version": "ap2-hp-passive-public-capture/1",
                "records": deepcopy(self.records), "observation_errors": deepcopy(self.errors),
                "observation_complete_at_wrapper": self.capture_complete,
                "native_hook_placement_verified": False,
                "transport_peer_ownership_verified": False,
                "native_qualification_established": False}
