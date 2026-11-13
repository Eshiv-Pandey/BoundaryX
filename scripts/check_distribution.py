"""Check the tracked source artifact without printing possible credential values.

This is a bounded publication check, not a guarantee that every possible secret
has been detected. Original archive manifests under provenance are ledgers of
local preservation, not claims that every original file is redistributed.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from boundaryx.core.evidence import digest, publish, read, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf8").split("\0")
    paths = [p for p in paths if p]
    issues = []
    archived_syntax_failures = []
    compiled = 0
    largest = 0
    sources = [str(ROOT), str(ROOT.parent / "Ai_Interoperability"), str(Path.home()), str(Path(sys.executable).parent)]
    machine_paths = [s.lower().encode() for source in sources
                     for s in (source, source.replace("\\", "/"), source.replace("\\", "\\\\"))]
    credentials = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|"
                             rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")
    for name in paths:
        path = ROOT / name
        parts = Path(name).parts
        if (any(p in ("node_modules", "__pycache__", "results/local") or p.startswith(".venv") for p in parts)
                or name.startswith("results/local/")
                or path.name in ("AGENTS.md", "USER_INSTRUCTIONS.md", "CONTRIBUTION_RULES.md")
                or path.name == ".env" or path.name.startswith(".env.")):
            issues.append({"path": name, "kind": "local-only file tracked"})
        if not path.is_file():
            issues.append({"path": name, "kind": "tracked file missing"})
            continue
        raw = path.read_bytes()
        largest = max(largest, len(raw))
        if len(raw) >= 50 * 1024 * 1024:
            issues.append({"path": name, "kind": "oversized Git blob"})
        if credentials.search(raw):
            issues.append({"path": name, "kind": "credential-pattern candidate; inspect locally"})
        if any(p in raw.lower() for p in machine_paths):
            issues.append({"path": name, "kind": "machine command/configuration path"})
        if name.endswith(".py"):
            try:
                ast.parse(raw, filename=name)
                compiled += 1
            except SyntaxError as exc:
                original_copies = ["runs/supervisor-handoff-20261113/admission-demo-001/" + prefix
                                   + "/interoperability/ap2_hp_gemini_source_graph_v1.py"
                                   for prefix in ("benchmark/source", "prepared/src", "replay/source")]
                finding = {"path": name, "kind": "Python syntax", "line": exc.lineno, "sha256": digest(raw)}
                if (name in original_copies
                        and digest(raw) == "c07f3652fef746d654587da3bccf04b8055fef2f5ef32b3081cb91716f3d0c88"):
                    archived_syntax_failures.append(finding)
                else:
                    issues.append(finding)
    manifests = 0
    members = 0
    for name in paths:
        if (name.endswith("/manifest.json")
                and name.startswith(("runs/", "results/development/", "benchmarks/heldout/"))):
            path = ROOT / name
            if read(path).get("files"):
                try:
                    members += verify_manifest(path.parent)
                    manifests += 1
                except (ValueError, OSError, KeyError) as exc:
                    issues.append({"path": name, "kind": "manifest validation", "reason": str(exc)})
    links = 0
    active_docs = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    for path in active_docs:
        for target in re.findall(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", path.read_text(encoding="utf8")):
            if re.match(r"^[a-z]+:|^#", target):
                continue
            target = target.split("#")[0]
            links += 1
            if target and not (path.parent / target).exists():
                issues.append({"path": path.relative_to(ROOT).as_posix(), "kind": "missing active link", "target": target})
    schema = read(ROOT / "benchmarks/schemas/task-contract.schema.json")
    task_count = 0
    for name in ("benchmarks/development/human-review/tasks.json", "benchmarks/heldout/v1/tasks.json",
                 "benchmarks/heldout/v2/tasks.json"):
        tasks = read(ROOT / name)["tasks"]
        seen = set()
        for task in tasks:
            identifier = task.get("id")
            valid = set(schema["required"]).issubset(task) and set(task).issubset(schema["properties"])
            for key, rule in schema["properties"].items():
                value = task.get(key)
                if "enum" in rule:
                    valid &= value in rule["enum"]
                if rule.get("type") == "string":
                    valid &= isinstance(value, str) and len(value) >= rule.get("minLength", 0)
                if rule.get("type") == "array":
                    valid &= isinstance(value, list) and len(value) >= rule.get("minItems", 0) and all(isinstance(v, str) for v in value)
                if rule.get("type") == "object":
                    valid &= isinstance(value, dict)
            if not valid or identifier in seen:
                issues.append({"path": name, "kind": "declared task schema or duplicate ID", "task": identifier})
            seen.add(identifier)
            task_count += 1
    result = {"schema_version": "boundaryx_distribution_check_v1", "status": "Completed" if not issues else "Not Established",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(), "tracked_files_checked": len(paths),
              "python_sources_compiled": compiled, "largest_file_bytes": largest,
              "evidence_manifests_verified": manifests, "manifest_members_verified": members,
              "active_document_links_checked": links, "task_schema_instances_checked": task_count,
              "task_count_note": "24 development examples and two versions of 20 held-out proposals; not 64 independent evaluations",
              "checker_sha256": digest(Path(__file__).read_bytes()), "issues": issues,
              "archived_syntax_failures": archived_syntax_failures,
              "archive_note": "Three exact original copies of an unrelated malformed AP2 module remain historical evidence; excluded from the functional package and never repaired to hide failure",
              "limits": ["Finite credential-pattern and current-machine-path scan, not a universal secret detector",
                         "Syntax/schema/integrity checks do not establish human gold or scientific correctness",
                         "Checks tracked working-tree bytes; clean-clone verification checks committed publication bytes"]}
    publish(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('issues', 'archived_syntax_failures')}
                     | {'issue_count': len(issues), 'first_issues': issues[:10],
                        'archived_syntax_failure_count': len(archived_syntax_failures)}))
    return bool(issues)


if __name__ == "__main__":
    raise SystemExit(main())
