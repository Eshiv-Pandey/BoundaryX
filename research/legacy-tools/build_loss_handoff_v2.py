"""Build and execute an allowlisted portable supervisor handoff before zipping it.

Copies immutable evidence bytes and required source, creates a fresh pip-free
Python environment, and runs the delivered entrypoint from the copied root.
The original research allocations and unrelated files are never changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_loss_software_v2 import SUITES, CORE
from verify_loss_package_v2 import verify_zip

RUNS = ["diagnostics-final-001", "protocol-main-001", "parts-main-001", "final-verification-001",
        "parts-verification-001", "software-validation-001", "admission-demo-001", "baseline-verification-001",
        "protocol-native-smoke-001", "protocol-bridge-smoke-001"]
SCRIPTS = ["run_loss_benchmark_v1.py", "run_loss_diagnostics_v2.py", "run_loss_protocol_v2.mjs", "run_loss_parts_v2.mjs",
           "loss_protocol_receiver_v2.py", "verify_loss_release_v2.py", "verify_loss_parts_v2.py", "check_loss_software_v2.py",
           "verify_loss_benchmark_v1.py", "build_loss_benchmark_retained_v1.py", "capture_loss_benchmark_inputs_v1.py",
           "build_loss_figures_v2.py", "build_loss_review_data_v2.py", "check_loss_explorer_v2.mjs",
           "run_shared_admission_demo_v1.py", "run_loss_handoff_v2.py", "build_loss_handoff_v2.py",
           "verify_loss_package_v2.py", "archive_loss_explorer_review_v2.py", "loss_json_io_v2.py", "generate_refinement_scaling_v1.py"]
DENIED = {"agents.md", "contribution_rules.md", "user_instructions.md", ".env", ".git", ".venv", "node_modules", "__pycache__"}


def read(path):
    return json.loads(path.read_bytes())


def identity(path):
    digest, total = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
            total += len(chunk)
    return {"bytes": total, "sha256": digest.hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_links(package):
    checked = 0
    for relative in ("SUPERVISOR_HANDOFF_2026-11-13.md", "benchmark/loss-v2/README.md", "THIRD_PARTY_NOTICES.md", "demo/benchmark-v2/README.md"):
        document = package / relative
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            if target.startswith(("http:", "https:", "#")):
                continue
            path = (document.parent / target.split("#")[0]).resolve()
            require(path.is_relative_to(package.resolve()) and path.exists(), "broken/outside report link: " + target)
            checked += 1
    html = package / "demo/benchmark-v2/index.html"
    for target in re.findall(r'(?:href|src)="([^"]+)"', html.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "#")):
            continue
        require((html.parent / target).exists(), "broken explorer link: " + target)
        checked += 1
    data = read(package / "demo/benchmark-v2/data.json")
    for rows in (data["protocolCells"], data["partsCells"], data["diagnosticCells"]):
        for row in rows:
            require((package / row["raw_path"]).is_file(), "missing explorer raw capture")
            checked += 1
    for source in data["sources"]:
        require(identity(package / source["path"])["sha256"] == source["sha256"], "explorer data provenance mismatch")
    for provenance in (package / "reports/supervisor-20261113/images").glob("*.provenance.json"):
        value = read(provenance)
        if "capture_path" in value:
            require(identity(package / value["capture_path"])["sha256"] == value["capture_sha256"], "screenshot origin mismatch")
        for source in value["sources"]:
            require(identity(package / source["path"])["sha256"] == source["sha256"], "figure provenance mismatch")
    return checked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--validation-output", type=Path, required=True)
    parser.add_argument("--python-env", type=Path, required=True)
    args = parser.parse_args()
    package, archive, validation, python_env = [p.resolve() for p in (args.package, args.zip, args.validation_output, args.python_env)]
    require(package.is_relative_to(ROOT) and package != ROOT, "package must be a new directory inside workspace")
    for target in (package, archive, validation, python_env):
        require(not target.exists(), "preserve existing output: " + str(target))
    package.mkdir(parents=True)
    copied = set()

    def copy(relative):
        name = PurePosixPath(relative)
        require(not name.is_absolute() and ".." not in name.parts, "unsafe selected path")
        require(not any(p.lower() in DENIED for p in name.parts), "local/private material excluded: " + relative)
        source, target = ROOT.joinpath(*name.parts), package.joinpath(*name.parts)
        require(source.is_file() and not source.is_symlink() and not source.is_junction(), "expected regular source: " + relative)
        if relative in copied:
            require(identity(source) == identity(target), "source changed while copying: " + relative)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as source_stream, target.open("xb") as stream:
            while chunk := source_stream.read(65536):
                stream.write(chunk)
        copied.add(relative)

    def tree(relative, suffix=None):
        directory = ROOT / relative
        for source in sorted(directory.rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts and (suffix is None or source.suffix == suffix):
                copy(source.relative_to(ROOT).as_posix())

    for file in ("SUPERVISOR_HANDOFF_2026-11-13.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml",
                 "benchmark/loss-v2/README.md", "benchmark/loss-v1/development-cases.json", "benchmark/loss-v1/retained-manifest.json",
                 "docs/research/loss-benchmark-metrics-v1.md", "reports/supervisor-20261113/packaging-first-attempt.json",
                 "reports/supervisor-20261113/packaging-second-attempt.json", "reports/supervisor-20261113/packaging-third-attempt.json"):
        copy(file)
    for script in SCRIPTS:
        copy("scripts/" + script)
    for test in SUITES + CORE:
        copy("tests/" + test + ".py")
    copy("tests/test_loss_json_io_v2.py")
    tree("src/interoperability", ".py")
    tree("examples", ".json")
    tree("benchmark/loss-v1/retained-inputs")
    tree("runs/loss-benchmark-v1/fresh-development-003")
    tree("runs/loss-benchmark-retained-v1/20261112T112741770806Z-3326eed1")
    for run in RUNS:
        tree("runs/supervisor-handoff-20261113/" + run)
    tree("demo/benchmark-v2")
    tree("reports/supervisor-20261113/images")
    tree("reports/supervisor-20261113/ui-validation")
    for name in ("external/a2a-to-mcp/LICENSE", "external/mcp-a2a/LICENSE", "external/mcp-a2a/src/client/shape.ts"):
        copy(name)
    for run in ("diagnostics-final-001", "protocol-main-001", "parts-main-001"):
        allocation = read(ROOT / "runs/supervisor-handoff-20261113" / run / "allocation.json")
        for source in allocation.get("source_files", allocation.get("sources", [])):
            copy(source["path"])
    if (ROOT / "DESIGN.md").exists():
        copy("DESIGN.md")
    if (ROOT / ".impeccable/design.json").exists():
        copy(".impeccable/design.json")

    require(not list(package.rglob("node_modules")), "clean package accidentally contains Node installation")
    print(json.dumps({"copied_files": len(copied), "copied_bytes": sum((package / x).stat().st_size for x in copied)}), flush=True)
    venv.EnvBuilder(with_pip=False).create(python_env)
    python = python_env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    command = [str(python), "-B", str(package / "scripts/run_loss_handoff_v2.py"), "--output", str(validation), "--reproduce"]
    print("Running delivered entrypoint from copied root with fresh pip-free Python", flush=True)
    process = subprocess.run(command, cwd=package, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1500)
    logs = ROOT / "reports/supervisor-20261113"
    logs.mkdir(parents=True, exist_ok=True)
    log_names = [validation.name + "-build-stdout.txt", validation.name + "-build-stderr.txt"]
    for name, blob in zip(log_names, (process.stdout, process.stderr)):
        with (logs / name).open("xb") as stream:
            stream.write(blob)
    require(process.returncode == 0, "portable entrypoint failed; inspect retained output/logs")
    result = read(validation / "result.json")
    require(result["status"] == "passed" and result["executed_stages"] == 7, "incomplete portable reproduction")
    io_controls = json.loads((validation / "streaming-io-controls-stdout.txt").read_text(encoding="utf-8").splitlines()[-1])
    require(io_controls == {"status": "passed", "tests": 5, "failures": 0, "errors": 0}, "streaming IO controls incomplete")
    software = read(validation / "software/result.json")
    require(software["passed_tests"] >= 278 and software["passed_tests"] + software["skipped_tests"] == 279, "software census changed")
    fresh = read(validation / "fresh-diagnostics/results.json")
    require(fresh["episodes"] == 1920 and fresh["repair_interventions"] == 6400, "fresh diagnostic census changed")
    admission = read(validation / "fresh-admission-replay/result.json")
    require(admission["status"] == "passed", "portable admission/replay failed")
    receipt = {"schema_version": "loss_portable_delivery_validation_v2", "status": "passed", "completed_utc": datetime.now(timezone.utc).isoformat(),
               "clean_environment": "new venv without pip or installed third-party packages", "bridge_installations_present": False,
               "executed_from_copied_package_root": True, "pipeline_stages": result["executed_stages"],
               "streaming_io_controls_passed": 5, "io_adapter_sources": result["io_adapter_sources"],
               "software_passed": software["passed_tests"], "software_skipped": software["skipped_tests"],
               "fresh_diagnostic_episodes": fresh["episodes"], "fresh_repair_interventions": fresh["repair_interventions"],
               "admission_replay": "passed", "model_calls": 0, "live_protocol_rerun": False,
               "scope": "Clean copied-package execution, saved protocol regrading and local finite reproduction. Not a fresh bridge run, independent human validation or new held-out experiment."}
    write(logs / "delivery-validation.json", receipt)
    copy("reports/supervisor-20261113/delivery-validation.json")
    for name in log_names:
        copy("reports/supervisor-20261113/" + name)
    # Preserve compact verification receipts; full repeated local run stays in the workspace.
    for relative in ("result.json", "software/result.json", "software/benchmark-stdout.txt", "software/benchmark-stderr.txt",
                     "software/core-stdout.txt", "software/core-stderr.txt", "recorded-tasks/verification.json", "recorded-artifacts/verification.json",
                     "check-fresh-diagnostics/verification.json", "fresh-admission-replay/replay-comparison.json",
                     "streaming-io-controls-stdout.txt", "streaming-io-controls-stderr.txt"):
        target = package / "reports/supervisor-20261113/portable-check" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write((validation / relative).read_bytes())
    receipt["relative_links_checked"] = audit_links(package)
    write(package / "release-status.json", {"status": "complete_for_declared_development_framework_scope", "scientific_study_complete": False,
        "criteria": {"final_allocations_complete": True, "independent_software_regrading": True, "software_suites_pass": True,
                     "fresh_finite_reproduction": True, "finite_admission_replay": True, "figures_and_report": True,
                     "portable_raw_links": True, "no_model_or_provider_dependency_for_replay": True}, "validation": receipt})
    files = [{"path": p.relative_to(package).as_posix(), **identity(p)} for p in sorted(package.rglob("*")) if p.is_file()]
    write(package / "release-manifest.json", {"schema_version": "loss_supervisor_package_manifest_v2", "files": files,
                                               "total_files": len(files), "total_bytes": sum(x["bytes"] for x in files)})
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for p in sorted(package.rglob("*")):
            if p.is_file():
                zipped.write(p, "interop-benchmark-20261113/" + p.relative_to(package).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        require(zipped.testzip() is None, "ZIP CRC check failed")
    zip_verification = verify_zip(archive)
    result = {"status": "passed", "package": str(package), "archive": str(archive), **identity(archive),
              "payload_files": len(files), "payload_bytes": sum(x["bytes"] for x in files), "relative_links_checked": receipt["relative_links_checked"],
              "validation_output": str(validation), "clean_python_env": str(python_env), "zip_verification": zip_verification}
    write(archive.with_suffix(".build.json"), result)
    with archive.with_suffix(".sha256").open("x", encoding="ascii") as stream:
        stream.write(result["sha256"] + "  " + archive.name + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
