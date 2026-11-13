from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

from boundaryx.core.evidence import digest, publish


def execute(root: Path, command: list[str], output: Path, timeout: int = 1800) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    began = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    error = None
    try:
        process = subprocess.run(command, cwd=root, capture_output=True, timeout=timeout)
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr, code = exc.stdout or b"", exc.stderr or b"", None
        error = "timeout"
    except OSError as exc:
        stdout, stderr, code = b"", str(exc).encode(), None
        error = "launch_error"
    for name, raw in (("stdout.txt", stdout), ("stderr.txt", stderr)):
        (output / name).write_bytes(raw)
    result = {"status": "Completed" if code == 0 else "Not Established",
              "command": command, "started_utc": began,
              "completed_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "os": platform.system(),
              "wall_seconds": time.perf_counter() - clock, "exit_code": code, "error": error,
              "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr)}
    publish(output / "receipt.json", result)
    return result
