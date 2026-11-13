"""Evidence utilities, independently implemented without legacy scorer imports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class EvidenceError(ValueError):
    """Malformed or insufficient evidence; never a fabricated task failure."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise EvidenceError(f"Non-finite JSON number: {value}")


def parse(raw: str | bytes) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("Invalid JSON evidence") from exc


def read(path: Path) -> Any:
    return parse(path.read_bytes())


def same(left: Any, right: Any) -> bool:
    """Object order is immaterial; array order, multiplicity and types matter."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return bool(left == right)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def member(root: Path, relative: str) -> Path:
    posix, windows = PurePosixPath(relative), PureWindowsPath(relative)
    if (not relative or posix.is_absolute() or windows.drive or "\\" in relative
            or ":" in relative or any(p in ("", ".", "..") for p in relative.split("/"))):
        raise EvidenceError("Unsafe manifest member")
    current = root
    if root.is_symlink() or root.is_junction():
        raise EvidenceError("Linked evidence root")
    for part in posix.parts:
        current /= part
        if current.is_symlink() or current.is_junction():
            raise EvidenceError("Linked manifest member")
    if not current.resolve().is_relative_to(root.resolve()):
        raise EvidenceError("Manifest member escapes root")
    return current


def verify_manifest(root: Path, name: str = "manifest.json") -> int:
    value = read(root / name)
    rows = value.get("files", [])
    if not rows:
        raise EvidenceError("Empty manifest")
    seen: set[str] = set()
    for row in rows:
        relative = row["path"]
        if relative in seen:
            raise EvidenceError("Duplicate manifest member")
        seen.add(relative)
        raw = member(root, relative).read_bytes()
        if digest(raw) != row["sha256"] or len(raw) != row["bytes"]:
            raise EvidenceError(f"Manifest mismatch: {relative}")
    return len(rows)


def publish(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")
