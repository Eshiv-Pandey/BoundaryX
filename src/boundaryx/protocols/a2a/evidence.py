from typing import Any


def public_task(packet: dict[str, Any]) -> dict[str, Any]:
    result = packet.get("result", packet)
    return dict(result.get("task", result))


def identity(task: dict[str, Any]) -> tuple[Any, Any]:
    return task.get("id"), task.get("contextId", task.get("context_id"))
