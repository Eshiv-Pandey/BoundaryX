"""Create a suspended Windows child inside one task-owned Job Object.

The job owns descendants before the first child instruction runs. Cleanup uses
job/process handles, never a process found by name or an unrelated PID.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
from copy import deepcopy
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time


class _IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _Limits(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", w.DWORD),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _Limits), ("IoInfo", _IO)] + [(name, ctypes.c_size_t) for name in (
        "ProcessMemoryLimit", "JobMemoryLimit", "PeakProcessMemoryUsed", "PeakJobMemoryUsed")]


class _Startup(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR)] + [
        (name, w.DWORD) for name in ("dwX", "dwY", "dwXSize", "dwYSize", "dwXCountChars", "dwYCountChars", "dwFillAttribute", "dwFlags")
    ] + [("wShowWindow", w.WORD), ("cbReserved2", w.WORD), ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
         ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class _Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_longlong) for name in (
        "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime"
    )] + [(name, ctypes.c_uint32) for name in (
        "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses"
    )]


def _error(operation):
    code = getattr(ctypes, "get_last_error", lambda: 0)()
    return OSError(code, "owned Windows operation failed: " + operation)


class WindowsJob:
    def __init__(self):
        if sys.platform != "win32":
            raise ValueError("This source runner requires a native Windows Job Object")
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
            "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD,
                                ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(_Startup), ctypes.POINTER(_ProcessInfo)], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.job = self.api.CreateJobObjectW(None, None)
        if not self.job:
            raise _error("CreateJobObjectW")
        self.process = None
        self.thread = None
        self.pid = None
        self.argv = None
        self.closed = False
        self.created = False
        self.assigned = False
        self.resumed = False
        self.launch_attempted = False
        self.forced = False
        self.launch_failure = None
        self._empty_verified = False
        self._last_observation = None
        self._last_report = None
        self._finish_calls = 0
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE; breakaway is not enabled.
        if not self.api.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = _error("SetInformationJobObject")
            self._failure_cleanup(error, self.close)
            raise error

    def _failure_cleanup(self, error, action):
        """Both primary and unexpected cleanup exceptions carry live authority."""
        error.owned_job = self  # Attach before cleanup can fail or be interrupted.
        try:
            cleanup = action()
        except BaseException as cleanup_error:
            cleanup_error.owned_job = self
            cleanup_error.owned_primary_error_type = type(error).__name__
            cleanup = {"status": "cleanup_exception", "errors": [type(cleanup_error).__name__],
                       "handles_closed": self.closed, "authority_retained": not self.closed,
                       "owned_handles": self._handles(), "job_empty_observed": self._empty_verified}
            cleanup_error.owned_cleanup = cleanup
            if self.launch_failure is not None:
                self.launch_failure["cleanup"] = cleanup
            raise
        error.owned_cleanup = cleanup
        return cleanup

    def launch(self, argv, cwd, stdout, stderr):
        if self.closed or self.launch_attempted or not argv or any(type(value) is not str or not value or "\0" in value for value in argv):
            raise ValueError("Require one exact launch argv and an unused owned job")
        if not Path(argv[0]).is_absolute() or not Path(cwd).is_absolute():
            raise ValueError("Executable and cwd must be absolute")
        import msvcrt
        self.launch_attempted = True
        info, startup = _ProcessInfo(), _Startup()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = 0x100  # STARTF_USESTDHANDLES
        failure, stage, restore_errors = None, "stdio", []
        handles, prior = [], []
        try:
            with open(os.devnull, "rb") as null:
                try:
                    handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in (null, stdout, stderr)]
                    for handle in handles:
                        prior.append(os.get_handle_inheritable(handle))
                    stage = "inherit_stdio"
                    for handle in handles:
                        os.set_handle_inheritable(handle, True)
                    startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
                    command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
                    flags = 0x4 | 0x08000000 | 0x200  # SUSPENDED + NO_WINDOW + NEW_PROCESS_GROUP
                    stage = "create"
                    if not self.api.CreateProcessW(argv[0], command, None, None, True, flags, None, str(cwd), ctypes.byref(startup), ctypes.byref(info)):
                        raise _error("CreateProcessW")
                    # Store authority before any later API or restoration can fail.
                    self.created = True
                    self.process, self.thread = info.hProcess, info.hThread
                    self.pid, self.argv = int(info.dwProcessId), list(argv)
                    if not self.process or not self.thread or self.pid <= 0:
                        raise ValueError("created process information is incomplete")
                    stage = "assign"
                    if not self.api.AssignProcessToJobObject(self.job, self.process):
                        raise _error("AssignProcessToJobObject")
                    self.assigned = True
                    stage = "resume"
                    previous = self.api.ResumeThread(self.thread)
                    if type(previous) is not int or previous != 1:
                        raise _error("ResumeThread")
                    self.resumed = True
                except BaseException as error:
                    failure = error
                finally:
                    for handle, value in zip(handles, prior):
                        try:
                            os.set_handle_inheritable(handle, value)
                        except BaseException as error:
                            restore_errors.append({"handle": int(handle), "error_type": type(error).__name__})
        except BaseException as error:
            if failure is None:
                failure, stage = error, "stdio_close"
        if restore_errors and failure is None:
            failure, stage = OSError("owned launch could not restore stdio handle flags"), "restore_stdio"
        if failure is None:
            try:
                if not self.api.CloseHandle(self.thread):
                    raise _error("CloseHandle(thread)")
                self.thread = None
            except BaseException as error:
                failure, stage = error, "close_thread"
        if failure is not None:
            self.launch_failure = {"stage": stage, "error_type": type(failure).__name__, "restore_errors": restore_errors}
            cleanup = self._failure_cleanup(failure,
                (lambda: self.finish(graceful_seconds=0, forced_seconds=5)) if self.created else self.close)
            self.launch_failure["cleanup"] = cleanup
            raise failure
        return self.pid

    def poll(self):
        if self.closed or self.process is None:
            raise ValueError("Require the open owned process handle")
        result = self.api.WaitForSingleObject(self.process, 0)
        if type(result) is not int:
            raise ValueError("malformed process wait result")
        if result == 258:
            return None
        if result != 0:
            raise _error("WaitForSingleObject")
        code = w.DWORD()
        if not self.api.GetExitCodeProcess(self.process, ctypes.byref(code)):
            raise _error("GetExitCodeProcess")
        return int(code.value)

    def active_processes(self):
        """Independent Job accounting query, separate from the PID-list query."""
        if self.closed or self.job is None:
            raise ValueError("Job handle is closed")
        accounting, returned = _Accounting(), w.DWORD()
        if not self.api.QueryInformationJobObject(self.job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), ctypes.byref(returned)):
            raise _error("QueryInformationJobObject(accounting)")
        return int(accounting.ActiveProcesses)

    def members(self):
        if self.closed or self.job is None:
            raise ValueError("Job handle is closed")
        capacity = 32
        while capacity <= 4096:
            buffer = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            returned = w.DWORD()
            ok = self.api.QueryInformationJobObject(self.job, 3, buffer, len(buffer), ctypes.byref(returned))
            assigned, listed = struct.unpack_from("<II", buffer.raw)
            if ok and listed <= capacity and listed == assigned:
                values = (ctypes.c_size_t * listed).from_buffer_copy(buffer.raw, 8)
                pids = [int(value) for value in values]
                if any(pid <= 0 for pid in pids) or len(set(pids)) != len(pids):
                    raise ValueError("malformed or duplicated owned Job PID list")
                return pids
            if not ok and ctypes.get_last_error() != 234:
                raise _error("QueryInformationJobObject(PID list)")
            capacity = max(capacity * 2, assigned)
        raise ValueError("Owned group observation exceeds the bounded member limit")

    def _observe(self):
        code = self.poll()
        active = self.active_processes()
        pids = self.members()
        observation = {"returncode": code, "main_handle_signaled": code is not None,
                       "active_processes": active, "members": pids}
        self._last_observation = observation
        self._empty_verified = code is not None and type(active) is int and active == 0 and pids == []
        return observation

    def _handles(self):
        return {"job": self.job, "process": self.process, "thread": self.thread}

    def finish(self, graceful_seconds=20.0, forced_seconds=5.0):
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (graceful_seconds, forced_seconds)):
            raise ValueError("Cleanup waits must be finite and nonnegative")
        self._finish_calls += 1
        report = {"schema_version": "windows-owned-job-cleanup/1", "pid": self.pid, "argv": self.argv,
                  "forced": self.forced, "returncode": None, "members": None, "active_processes": None,
                  "main_handle_signaled": False, "job_empty_observed": False, "handles_closed": self.closed,
                  "authority_retained": not self.closed, "assigned_to_owned_job": self.assigned,
                  "cleanup_attempt": self._finish_calls, "observation_reused": False, "errors": []}
        if self.closed or self._empty_verified:
            report.update(deepcopy(self._last_observation or {}))
            report["job_empty_observed"], report["observation_reused"] = self._empty_verified, True
        elif self.created:
            def monitor(seconds):
                deadline = time.monotonic() + seconds
                while True:
                    try:
                        report.update(self._observe())
                    except (OSError, ValueError) as error:
                        report["errors"].append(type(error).__name__)
                        return False
                    if self._empty_verified:
                        return True
                    if time.monotonic() >= deadline:
                        return False
                    time.sleep(.05)

            if not monitor(graceful_seconds):
                self.forced = True  # Sticky, including a failed termination and every retry.
                operation = "TerminateJobObject" if self.assigned else "TerminateProcess"
                handle = self.job if self.assigned else self.process
                try:
                    if not handle or not getattr(self.api, operation)(handle, 1):
                        raise _error(operation)
                except (OSError, ValueError) as error:
                    report["errors"].append(operation + ":" + type(error).__name__)
                else:
                    monitor(forced_seconds)  # Always observe once, even with a zero deadline.
            report["job_empty_observed"] = self._empty_verified
        if not self.created or self._empty_verified:
            closing = self.close()
            report["errors"].extend(closing["errors"])
        report.update({"forced": self.forced, "handles_closed": self.closed,
                       "authority_retained": not self.closed, "owned_handles": self._handles()})
        self._last_report = deepcopy(report)
        return report

    def close(self):
        """Release only unlaunched or positively empty authority; never force by close."""
        report = {"handles_closed": self.closed, "authority_retained": not self.closed, "errors": []}
        if self.closed:
            return report
        if self.created and not self._empty_verified:
            report["errors"].append("OwnedAuthorityNotQualifiedEmpty")
            return report
        for name in ("thread", "process", "job"):
            handle = getattr(self, name)
            if handle is None:
                continue
            try:
                if not self.api.CloseHandle(handle):
                    raise _error("CloseHandle(" + name + ")")
            except (OSError, ValueError) as error:
                report["errors"].append("CloseHandle(" + name + "):" + type(error).__name__)
                break
            setattr(self, name, None)
        self.closed = all(value is None for value in self._handles().values())
        report.update({"handles_closed": self.closed, "authority_retained": not self.closed,
                       "owned_handles": self._handles()})
        return report
