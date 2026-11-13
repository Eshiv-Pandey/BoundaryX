"""Receiver process: evaluates only the supplied observation, never case gold."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from scripts.run_loss_benchmark_v1 import receiver_decision

if __name__ == "__main__":
    wire = json.load(sys.stdin)
    try:
        result = receiver_decision(wire)
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        result = {"task_id": wire.get("task", {}).get("task_id"),
                  "target": wire.get("task", {}).get("target"),
                  "status": "receiver_error", "answer": None,
                  "error": type(exc).__name__ + ": " + str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
