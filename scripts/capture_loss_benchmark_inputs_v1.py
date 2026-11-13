"""Copy manifest-pinned retained inputs into a fresh portable mirror, without replay."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys

INVENTORY_NAME = "inventory.json"
MANIFEST_SCHEMA = "loss_benchmark_retained_manifest_v1"
NOTICE = ("Byte-preserving retained-input export only; no provider, model, native protocol "
          "or archived source program is executed. This is not a fresh service experiment.")
PRIVATE_NAMES = {"agents.md", "user_instructions.md", "contribution_rules.md", "memory.md",
                 ".env", ".netrc", "_netrc", ".npmrc", ".pypirc", "credentials", "credentials.json",
                 "secrets.json", "secrets.yaml", "secrets.yml", "token.json", "tokens.json",
                 "id_rsa", "id_ed25519", "id_dsa", "private_key.pem", "private-key.pem"}
PRIVATE_DIRECTORIES = {".codex", ".agents", ".ssh", ".aws", ".azure", ".kube", "gcloud"}


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def identity(raw: bytes) -> dict:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def reject_link_ancestors(path: Path) -> None:
    for ancestor in (path.absolute(), *path.absolute().parents):
        if is_link(ancestor):
            raise ValueError("explicit path or ancestor cannot be a symlink or junction")


def strict_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest JSON key: " + key)
        result[key] = value
    return result


def validate_relative(raw: str) -> Path:
    """Reject ambiguous and escaping paths consistently on Windows and POSIX."""
    if type(raw) is not str or not raw or raw.strip() != raw:
        raise ValueError("pin path must be a nonempty relative string")
    if "\\" in raw or ":" in raw or any(ord(char) < 32 or char in '<>"|?*' for char in raw):
        raise ValueError("pin path cannot contain Windows separators, drives, streams or NUL")
    posix, windows = PurePosixPath(raw), PureWindowsPath(raw)
    parts = raw.split("/")
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(p in ("", ".", "..") for p in parts):
        raise ValueError("pin path escapes or ambiguously names the input root")
    lower = [part.casefold() for part in parts]
    if any(part in PRIVATE_DIRECTORIES for part in lower):
        raise ValueError("private local configuration directory is not exportable")
    name = lower[-1]
    if name in PRIVATE_NAMES or name.startswith(".env.") or name.startswith("credentials.") or name.startswith("service-account"):
        raise ValueError("credential or private local instruction path is not exportable")
    # Windows aliases can collapse distinct manifest paths or target devices.
    reserved = {"con", "prn", "aux", "nul", "conin$", "conout$",
                *("com" + str(i) for i in range(1, 10)), *("lpt" + str(i) for i in range(1, 10)),
                *(prefix + digit for prefix in ("com", "lpt") for digit in ("\u00b9", "\u00b2", "\u00b3"))}
    if any(part.endswith((".", " ")) or part.split(".")[0].casefold() in reserved for part in parts):
        raise ValueError("pin path uses a Windows device name or trailing alias")
    if len(parts) == 1 and name == INVENTORY_NAME:
        raise ValueError("pin path collides with the portable inventory")
    return Path(*parts)


def no_links_below(root: Path, candidate: Path) -> None:
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes the explicit root") from exc
    current = root
    if is_link(current):
        raise ValueError("explicit root cannot be a symlink or junction")
    for part in relative.parts:
        current = current / part
        if is_link(current):
            raise ValueError("symlink or junction is not exportable")
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("resolved path escapes the explicit root") from exc


def prepare_output(output: Path) -> Path:
    """Validate the intended absolute target before any allocation mutation."""
    absolute = output.absolute()
    reject_link_ancestors(absolute)
    if absolute.exists():
        raise FileExistsError("portable output already exists: " + str(absolute))
    if absolute.resolve(strict=False) != absolute:
        raise ValueError("output path must resolve to its explicit absolute target")
    return absolute


def capture(root: Path, manifest_path: Path, output: Path) -> dict:
    original_root = root.absolute()
    reject_link_ancestors(original_root)
    source_root = original_root.resolve(strict=True)
    if not source_root.is_dir():
        raise ValueError("source root must be a directory")
    target_root = prepare_output(output)
    reject_link_ancestors(manifest_path)
    manifest_file = manifest_path.resolve(strict=True)
    if not manifest_file.is_file():
        raise ValueError("manifest must be a regular file")
    manifest_raw = manifest_file.read_bytes()
    manifest = json.loads(manifest_raw, object_pairs_hook=strict_object)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("unsupported retained manifest schema")
    pins = manifest.get("source_files")
    if not isinstance(pins, list) or not pins:
        raise ValueError("manifest must contain nonempty source_files pins")
    prepared, seen = [], set()
    for pin in pins:
        if not isinstance(pin, dict) or set(pin) != {"path", "sha256"}:
            raise ValueError("source pin requires exactly path and sha256")
        relative = validate_relative(pin["path"])
        key = relative.as_posix().casefold()
        if key in seen:
            raise ValueError("duplicate or Windows-colliding source pin")
        seen.add(key)
        expected = pin["sha256"]
        if type(expected) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("source pin sha256 must be lowercase hexadecimal")
        source = source_root / relative
        no_links_below(source_root, source)
        if not source.is_file():
            raise ValueError("pinned source is missing or not a regular file: " + relative.as_posix())
        raw = source.read_bytes()
        record = {"path": relative.as_posix(), **identity(raw)}
        if record["sha256"] != expected:
            raise ValueError("pinned source hash mismatch: " + relative.as_posix())
        prepared.append((relative, raw, record))
    # All source paths and SHA pins are verified before output allocation. Using
    # those cached pinned bytes also prevents a later source mutation changing a copy.
    target_root.mkdir(parents=True, exist_ok=False)
    for relative, raw, record in prepared:
        destination = target_root / relative
        no_links_below(target_root, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        no_links_below(target_root, destination)
        with destination.open("xb") as handle:
            handle.write(raw)
        no_links_below(target_root, destination)
        if identity(destination.read_bytes()) != {key: record[key] for key in ("sha256", "bytes")}:
            raise ValueError("portable copy bytes/hash mismatch: " + relative.as_posix())
    expected_paths = {relative.as_posix() for relative, _, _ in prepared}
    actual_paths = {path.relative_to(target_root).as_posix() for path in target_root.rglob("*") if path.is_file()}
    if actual_paths != expected_paths:
        raise ValueError("portable mirror contains unexpected or missing files")
    inventory = {"schema_version": "loss_benchmark_portable_inputs_inventory_v1",
                 "notice": NOTICE, "captured_utc": datetime.now(timezone.utc).isoformat(),
                 "source_manifest": {"schema_version": MANIFEST_SCHEMA, **identity(manifest_raw), "pin_count": len(pins)},
                 "capture_script": identity(Path(__file__).read_bytes()),
                 "unique_file_count": len(prepared), "file_total_bytes": sum(len(raw) for _, raw, _ in prepared),
                 "byte_preserving": True, "service_execution": False,
                 "files": sorted((record for _, _, record in prepared), key=lambda record: record["path"])}
    with (target_root / INVENTORY_NAME).open("xb") as handle:
        handle.write(canonical(inventory) + b"\n")
    return inventory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument("--root", type=Path, required=True, help="original source root")
    parser.add_argument("--manifest", type=Path, required=True, help="existing retained manifest; resolved independently of root")
    parser.add_argument("--output", type=Path, required=True, help="fresh portable mirror root")
    args = parser.parse_args(argv)
    try:
        inventory = capture(args.root, args.manifest, args.output)
    except Exception as exc:
        print(f"retained-input export refused/failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"output": str(args.output.resolve()), "unique_file_count": inventory["unique_file_count"],
                      "file_total_bytes": inventory["file_total_bytes"], "inventory": INVENTORY_NAME,
                      "source_manifest_sha256": inventory["source_manifest"]["sha256"], "notice": NOTICE}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
