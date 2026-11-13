from typing import Any
from boundaryx.core.evidence import parse


def tool_result(packet: dict[str, Any]) -> dict[str, Any]:
    return dict(packet.get("result", packet))


def structured(result: dict[str, Any]) -> Any:
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    if len(content) == 1 and content[0].get("type") == "text":
        return parse(content[0]["text"])
    return result
