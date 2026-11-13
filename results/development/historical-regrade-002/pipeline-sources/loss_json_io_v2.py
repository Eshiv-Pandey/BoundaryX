"""Byte-equivalent streaming output for frozen Python diagnostic/checker entrypoints.

Only run_loss_benchmark_v1.write_new is replaced at runtime. Task definitions,
receiver, gold, conversion, scoring and verification functions are unchanged.
The handoff pipeline captures this wrapper's bytes and invocation separately.
"""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]
ALLOWED = {"verify_loss_release_v2.py", "run_loss_diagnostics_v2.py"}


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("xb") as stream:
        for chunk in encoder.iterencode(value):
            stream.write(chunk.encode("utf-8"))
        stream.write(b"\n")


def main():
    if sys.argv[1:] == ["--self-test"]:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName("test_loss_json_io_v2"))
        print(json.dumps({"status": "passed" if result.wasSuccessful() else "failed", "tests": result.testsRun,
                          "failures": len(result.failures), "errors": len(result.errors)}))
        return 0 if result.wasSuccessful() else 1
    if len(sys.argv) < 2 or sys.argv[1] not in ALLOWED:
        raise ValueError("wrapper requires a declared diagnostic/checker script")
    target, forwarded = sys.argv[1], sys.argv[2:]
    from scripts import run_loss_benchmark_v1 as frozen
    frozen.write_new = write_new
    module = importlib.import_module("scripts." + Path(target).stem)
    sys.argv = [str(ROOT / "scripts" / target), *forwarded]
    result = module.main()
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
