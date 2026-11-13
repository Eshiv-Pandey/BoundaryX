"""Opt-in resource observations for fresh benchmark workers.

The legacy benchmark worker stays unchanged. OS process peaks include startup,
imports and the input/result objects up to the observation before reply output.
They are not solver-only allocations or a measurement of the parent/whole host.
Unsupported or failed observations stay explicitly unavailable.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
import time
import traceback

from . import benchmark


SCHEMA = "benchmark-worker-resources/1"
TIMINGS = ("preparation_ns", "result_serialization_ns", "post_validation_ns")
WORKER_BOOT = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "from interoperability.benchmark_resources_v1 import worker; worker(sys.argv[2])"
)
MEMORY_SCOPE = (
    "OS process high-water mark observed after input post-check and result JSON "
    "serialization, before final reply output. Includes interpreter/import/input "
    "overhead; excludes the parent and other workers. Maxima across sequential "
    "workers are reported, never summed or called solver-only memory."
)
TIMING_SCOPE = (
    "preparation_ns starts at worker entry and includes job JSON loading, input "
    "digest and target import; wrapper/benchmark imports occur before entry. "
    "evaluation_ns covers the function attempt, including failures. Result JSON "
    "validation/serialization and input post-check are separate. worker_body_ns "
    "includes resource observation but excludes final reply serialization/write; "
    "worker_wall_ns includes process startup and output. These timings overlap "
    "and must not all be added together."
)


def process_peak() -> dict:
    """Read the current process's OS-maintained peak without a polling thread."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                        "PagefileUsage", "PeakPagefileUsage")]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel.GetCurrentProcess.argtypes = []
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise ctypes.WinError(ctypes.get_last_error())
            value, source = int(counters.PeakWorkingSetSize), "GetProcessMemoryInfo.PeakWorkingSetSize"
        elif sys.platform in ("linux", "darwin"):
            import resource
            value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            if sys.platform == "linux":
                value *= 1024
            source = "getrusage(RUSAGE_SELF).ru_maxrss"
        else:
            return {"status": "unavailable", "peak_resident_bytes": None,
                    "source": None, "reason": "unsupported_platform", "platform": sys.platform}
        if value <= 0:
            raise ValueError("OS returned a nonpositive peak")
        return {"status": "observed", "peak_resident_bytes": value,
                "source": source, "platform": sys.platform}
    except Exception as error:
        return {"status": "unavailable", "peak_resident_bytes": None,
                "source": None, "reason": type(error).__name__ + ": " + str(error),
                "platform": sys.platform}


def worker(job_path: str) -> None:
    """Run the same job contract with additional, equally applied observations."""
    tick = time.perf_counter_ns()
    job = benchmark._json(Path(job_path))
    model = job["runtime_manifest"]
    before = benchmark.digest(model)
    reply = {"status": "error", "input_sha256_before": before}
    timings = {name: None for name in TIMINGS}
    try:
        module = importlib.import_module(job["module"])
        package = Path(__file__).resolve().parent
        if not Path(module.__file__).resolve().is_relative_to(package):
            raise ValueError("worker imported an algorithm outside the captured package")
        function = getattr(module, job["entrypoint"])
        timings["preparation_ns"] = time.perf_counter_ns() - tick
        start = time.perf_counter_ns()
        try:
            if job["kind"] == "certificate":
                result = function(model, job["result"], job["now"])
            else:
                result = function(model, job["now"], **job.get("keyword_arguments", {}))
        finally:
            reply["evaluation_ns"] = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        try:
            json.dumps(result, allow_nan=False)
        finally:
            timings["result_serialization_ns"] = time.perf_counter_ns() - start
        reply.update(status="returned", result=result)
    except Exception as error:
        reply.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        start = time.perf_counter_ns()
        try:
            reply["input_sha256_after"] = benchmark.digest(model)
            reply["input_unchanged"] = reply["input_sha256_after"] == before
        except Exception:
            reply["input_unchanged"] = False
        timings["post_validation_ns"] = time.perf_counter_ns() - start
        reply["resources"] = {"schema_version": SCHEMA, "timings": timings, "memory": process_peak()}
        reply["worker_body_ns"] = time.perf_counter_ns() - tick
        benchmark._write(Path(job["reply_path"]), reply)


def summarize(executions: list[dict]) -> dict:
    """Include every attempted job; missing observations never become zero."""
    peaks, timings = [], {name: [] for name in TIMINGS}
    for execution in executions:
        resources = execution.get("resources")
        if resources is None:
            peaks.append(None)
            for values in timings.values():
                values.append(None)
            continue
        if resources.get("schema_version") != SCHEMA:
            raise ValueError("Unknown worker resource schema")
        memory = resources["memory"]
        value = memory["peak_resident_bytes"]
        if memory["status"] == "observed":
            if type(value) is not int or value <= 0 or not memory.get("source"):
                raise ValueError("Invalid observed process peak")
        elif memory["status"] != "unavailable" or value is not None:
            raise ValueError("Invalid unavailable process peak")
        peaks.append(value)
        for name, values in timings.items():
            value = resources["timings"][name]
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Invalid resource timing")
            values.append(value)
    observed = [value for value in peaks if value is not None]
    output = {"invocations": len(executions), "memory_scope": MEMORY_SCOPE, "timing_scope": TIMING_SCOPE,
              "peak_resident_bytes": {"samples": peaks, "observed": len(observed),
                  "missing": len(peaks) - len(observed), "maximum": max(observed) if observed else None}}
    for name, samples in timings.items():
        values = [value for value in samples if value is not None]
        output[name] = {"samples": samples, "observed": len(values),
                        "missing": len(samples) - len(values), "total": sum(values) if values else None}
    return output
