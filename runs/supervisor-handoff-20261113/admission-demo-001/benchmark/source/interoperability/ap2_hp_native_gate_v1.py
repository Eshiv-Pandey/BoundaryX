"""Stdlib-only AP2 native launch contracts and injected owned-group plumbing.

No original imports, key access, model calls or launches occur by import. Gates
bind current bytes/receipts; they do not authenticate provenance or establish a
safe threshold, qualified application, benchmark result or scientific claim.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat


SCHEMA = "ap2-hp-native-plan/1"
MINIMUMS = {"physical_available_bytes": 1024**3, "commit_available_bytes": 2 * 1024**3}
MODEL = "gemini-3.1-flash-lite-preview"
SOURCE_SHA = "ce0ffdd5503fddfe78ccb13d9c88e673ca2fdc3227e4ae460d3da10b2dc9406c"
SOURCE_PIN = "e1ea56db72a6385bce3e5c1112b3a56ce60acb43"
CERT_MANIFEST_SHA = "ee7016f043e5334bfd08dc65cc61cda503d233b9c455382e4f055cf6c970f105"
CERT_ASSETS = {
    "code/samples/certs/ds_cert_sdjwt.pem": {"bytes": 1066, "sha256": "a4b92cd66960d4ddcdcb8ca8b2887dafdec06cbcd42bc10fcc8ede41ffef1306", "git_blob": "b2b717529196fc44f1191b1aeedec64822505b3d"},
    "code/samples/certs/issuer_cert_sdjwt.pem": {"bytes": 1005, "sha256": "120abde3087907911c3c9de00c536657a6a503a88849a24653f6c35030c982ba", "git_blob": "dd1e7ba01972cf3ca5c566e4572294606d2992b4"},
}
PINNED_HELPERS = {
    "owned_job_helper": "67b5dc8190aee3a75b3c1954a530d0bba3edeb3bc64dc2770dd815173ecbd53a",
    "tcp_helper": "d1beef822af6ac1f3eb228a1dd69d3513dfb45274c5acc93192cbe0d5a7c44ed",
    "credential_helper": "0970d0614920d4820642b154d093d414b3f5a07164ca184d869950cca0035549",
}
SERVICES = (
    {"role": "merchant", "module": "roles.merchant_agent", "port": 8001, "rpc_path": "/a2a/merchant_agent"},
    {"role": "credentials", "module": "roles.credentials_provider_agent", "port": 8002, "rpc_path": "/a2a/credentials_provider"},
    {"role": "processor", "module": "roles.merchant_payment_processor_agent", "port": 8003, "rpc_path": "/a2a/merchant_payment_processor_agent"},
)
REFS = {"source_receipt", "environment_manifest", "usage_receipt", "interpreter", "powershell",
        "owned_job_helper", "tcp_helper", "credential_helper", "bootstrap_helper", "bootstrap_script",
        "usage_hook", "usage_hook_review", "windows_runtime", "supplementary_assets"}
PLAN_KEYS = {"schema_version", "run_id", "model", "output_root", "source_root", "services", "ownership_policy", *REFS}
PACKAGES = {"google-adk": "1.28.0", "a2a-sdk": "0.3.24", "google-genai": "1.66.0", "pydantic": "2.12.5"}


class GateError(ValueError):
    pass


def need(value, message):
    if not value:
        raise GateError(message)


def plain_json(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(plain_json(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and plain_json(item) for key, item in value.items())
    return False


def encoded(value):
    need(plain_json(value), "Contract requires plain JSON with integer counters and string keys.")
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate JSON object key.")
            value[key] = item
        return value
    def invalid(value):
        raise GateError("Nonfinite JSON number.")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    need(plain_json(result), "Receipt contains unsupported JSON types/counters.")
    return result


def utc(value):
    need(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value) is not None, "Aware UTC timestamp is required.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def time_now(value):
    need(type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timezone.utc.utcoffset(value), "Validation clock must be aware UTC.")
    return value


def regular(path, *, directory=False):
    need(isinstance(path, (str, Path)), "An absolute regular path is required.")
    path = Path(path)
    need(path.is_absolute(), "An absolute regular path is required.")
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "Linked/reparse launch paths are unsupported.")
    mode = path.stat().st_mode
    need(stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode), "Expected a regular directory/file.")
    return path


def reference(value, expected=None):
    need(isinstance(value, dict) and set(value) == {"path", "sha256"}, "Exact path/SHA256 artifact reference is required.")
    need(isinstance(value["sha256"], str) and re.fullmatch("[0-9a-f]{64}", value["sha256"]) is not None, "Invalid artifact digest.")
    if expected is not None:
        need(value["sha256"] == expected, "Frozen reviewed helper/source digest differs.")
    path = regular(value["path"])
    need(path.stat().st_size <= 64 * 1024 * 1024, "Oversized contract artifact.")
    raw = path.read_bytes()
    need(sha(raw) == value["sha256"], "Current artifact bytes differ from bound digest.")
    return raw


def tree(root, identities):
    root = regular(root, directory=True)
    need(isinstance(identities, dict) and 0 < len(identities) <= 100000, "Complete bounded file identities are required.")
    found = {}
    for path in root.rglob("*"):
        regular(path, directory=path.is_dir())
        if path.is_file():
            name = path.relative_to(root).as_posix()
            need("__pycache__" not in path.parts and path.suffix != ".pyc", "Cached bytecode is unsupported in the verified launch trees.")
            raw = path.read_bytes()
            found[name] = {"bytes": len(raw), "sha256": sha(raw)}
    for name, value in identities.items():
        relative = PurePosixPath(name)
        need(not relative.is_absolute() and relative.as_posix() == name and ".." not in relative.parts and ":" not in name and "\\" not in name, "Invalid relative file identity.")
        need(isinstance(value, dict) and set(value) == {"bytes", "sha256"} and type(value["bytes"]) is int, "Invalid file identity fields.")
    need(encoded(found) == encoded(identities), "Current launch tree membership/bytes differ from the complete manifest.")
    return found


def configuration_hash(plan):
    return sha(encoded({key: value for key, value in plan.items() if key != "usage_receipt"}))


def launch_binding(plan, role):
    need(role == "group" or role in {service["role"] for service in SERVICES}, "Unknown original service role.")
    return {"plan_sha256": sha(encoded(plan)), "configuration_sha256": configuration_hash(plan),
            "run_id": plan["run_id"], "role": role, "ownership_policy": plan["ownership_policy"]}


def validate_plan(plan, now):
    now = time_now(now)
    need(plain_json(plan) and isinstance(plan, dict) and set(plan) == PLAN_KEYS, "Exact native plan fields are required.")
    need(plan["schema_version"] == SCHEMA and plan["model"] == MODEL, "Original native plan schema/model required.")
    need(isinstance(plan["run_id"], str) and re.fullmatch("[0-9a-f]{32}", plan["run_id"]) is not None, "Bound prospective run identity is required.")
    need(encoded(plan["services"]) == encoded(list(SERVICES)), "Original service modules, order, ports and RPC paths must remain unchanged.")
    need(plan["ownership_policy"] == "per_service_windows_job_no_breakaway", "Exclusive Windows Job ownership policy required.")
    project = Path(__file__).absolute().parents[2]
    expected_implementations = {"bootstrap_helper": Path(__file__).absolute(),
        "windows_runtime": project / "src/interoperability/ap2_hp_windows_runtime_v1.py",
        "bootstrap_script": project / "scripts/boot_ap2_hp_service_v1.py",
        "owned_job_helper": project / "src/interoperability/windows_owned_job_v1.py",
        "tcp_helper": project / "src/interoperability/windows_tcp_ownership_v1.py",
        "credential_helper": project / "scripts/with_gemini_key.ps1",
        "source_receipt": project / "docs/research/source-evidence/ap2-procurement-screen-v1/source-result.json",
        "supplementary_assets": project / "docs/research/source-evidence/ap2-hp-cert-assets-v1/manifest.json"}
    for name, path in expected_implementations.items():
        need(isinstance(plan[name], dict) and Path(plan[name].get("path", "")) == path, "Executed bootstrap implementation origin differs.")
    output = Path(plan["output_root"])
    need(output.is_absolute(), "Absolute exclusive output root required.")
    regular(output.parent, directory=True)
    source = regular(plan["source_root"], directory=True)
    need(not source.is_relative_to(output) and not output.is_relative_to(source), "Source and case output trees must be separate.")
    expected_refs = {**PINNED_HELPERS, "source_receipt": SOURCE_SHA, "supplementary_assets": CERT_MANIFEST_SHA}
    raws = {name: reference(plan[name], expected_refs.get(name)) for name in REFS}
    original = strict_json(raws["source_receipt"])
    need(original.get("status") == "acquired" and original.get("commit") == SOURCE_PIN and original.get("acquired_files") == 134, "Pinned complete retained AP2 source receipt required.")
    files = {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in original["files"]}
    need(len(files) == 134, "Original AP2 source receipt membership is incomplete.")
    supplement = strict_json(raws["supplementary_assets"])
    need(supplement.get("schema_version") == "ap2-hp-public-cert-capture/1" and supplement.get("status") == "both_pinned_public_certificate_assets_captured"
        and supplement.get("commit") == SOURCE_PIN and isinstance(supplement.get("assets"), list), "Pinned supplementary AP2 certificate manifest required.")
    need(len(supplement["assets"]) == 2 and {item.get("source_path") for item in supplement["assets"]} == set(CERT_ASSETS), "Only the two exact original certificate paths may supplement source membership.")
    cert_manifest_root = Path(plan["supplementary_assets"]["path"]).parent
    tree_raw = regular(cert_manifest_root / "source-tree.json").read_bytes()
    need(sha(tree_raw) == supplement.get("source_tree_sha256"), "Supplementary certificate tree bytes differ from captured identity.")
    tree_entries = {item["path"]: item for item in strict_json(tree_raw)["tree"]}
    for item in supplement["assets"]:
        name, expected = item["source_path"], CERT_ASSETS[item["source_path"]]
        need(item.get("verified") is True and item.get("sha256") == expected["sha256"] and item.get("bytes") == expected["bytes"]
            and item.get("expected_git_blob") == item.get("actual_git_blob") == expected["git_blob"]
            and tree_entries.get(name, {}).get("sha") == expected["git_blob"], "Supplementary certificate pin/tree/blob identity differs.")
        raw = regular(source / name).read_bytes()
        need(sha(raw) == expected["sha256"] and len(raw) == expected["bytes"]
            and hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == expected["git_blob"], "Staged certificate bytes differ from the exact original asset.")
        need(name not in files, "Supplementary certificate overlaps the original source receipt.")
        files[name] = {"bytes": expected["bytes"], "sha256": expected["sha256"]}
    tree(source, files)
    environment = strict_json(raws["environment_manifest"])
    need(environment.get("schema_version") == "ap2-hp-native-environment/1" and environment.get("status") == "installed_hash_verified", "Installed AP2 environment manifest required.")
    need(environment.get("platform") == "win32" and encoded(environment.get("interpreter")) == encoded(plan["interpreter"]), "Platform/interpreter manifest binding differs.")
    need(all(environment.get("packages", {}).get(name) == version for name, version in PACKAGES.items()), "Original ADK/A2A/GenAI/Pydantic pins required.")
    environment_root = regular(environment.get("root"), directory=True)
    need(not output.is_relative_to(environment_root) and not environment_root.is_relative_to(output), "Environment and case output trees must be separate.")
    sites = regular(environment.get("site_packages"), directory=True)
    need(sites.is_relative_to(environment_root), "Site packages must belong to the exact installed environment.")
    tree(environment_root, environment.get("files"))
    usage = strict_json(raws["usage_receipt"])
    need(usage.get("schema_version") == "ap2-hp-model-usage-reservation/1" and usage.get("status") == "reserved_prospective_allowance", "Prospective model allowance reservation required.")
    need(usage.get("configuration_sha256") == configuration_hash(plan) and usage.get("model") == MODEL and usage.get("run_id") == plan["run_id"], "Usage reservation is not bound to this exact source/environment/launch configuration.")
    need(usage.get("counting_rules_verified") is True and usage.get("reset_rules_verified") is True, "Verified provider counting/reset rules required.")
    remaining, reserved = usage.get("remaining_model_calls"), usage.get("reserved_model_calls")
    need(type(remaining) is int and type(reserved) is int and 0 < reserved <= remaining, "Verified remaining allowance and positive bounded reservation required.")
    need(utc(usage.get("reserved_at_utc")) <= now < utc(usage.get("expires_at_utc")), "Usage reservation is future-dated or expired.")
    need(isinstance(usage.get("allowance_evidence"), list) and usage["allowance_evidence"], "Provider allowance evidence artifacts required.")
    for evidence in usage["allowance_evidence"]:
        reference(evidence)
    ledger = usage.get("ledger")
    reference(ledger)
    need(usage.get("hook_sha256") == plan["usage_hook"]["sha256"], "Usage hook identity differs from the reservation.")
    review = strict_json(raws["usage_hook_review"])
    need(review.get("status") == "source_review_closed" and review.get("hook_sha256") == plan["usage_hook"]["sha256"]
         and review.get("contract") == "enforce_before_every_provider_request", "Bound closed source review of the per-provider-request usage hook required.")
    return {"configuration_sha256": configuration_hash(plan), "source_files": len(files), "environment_files": len(environment["files"]),
            "site_packages": str(sites), "reserved_model_calls": reserved, "artifact_bytes_verified": True,
            "source_authentication_proven": False, "provider_entitlement_authenticated": False}


def validate_sample(sample):
    need(isinstance(sample, dict) and set(sample) == {"observed_at_utc", "monotonic_ns", *MINIMUMS}, "Exact typed memory sample required.")
    utc(sample["observed_at_utc"])
    need(type(sample["monotonic_ns"]) is int and sample["monotonic_ns"] >= 0, "Nonnegative integer monotonic sample required.")
    need(all(type(sample[key]) is int and sample[key] >= minimum for key, minimum in MINIMUMS.items()), "Available physical/commit headroom below fixed minima.")


def validate_gate(gate, binding, now):
    now = time_now(now)
    need(isinstance(gate, dict) and set(gate) == {"schema_version", "binding", "minimums", "samples"}, "Exact prospective resource receipt required.")
    need(gate["schema_version"] == "ap2-hp-native-resource-gate/1" and encoded(gate["binding"]) == encoded(binding), "Resource gate binding differs from exact prospective launch.")
    need(encoded(gate["minimums"]) == encoded(MINIMUMS) and isinstance(gate["samples"], list) and len(gate["samples"]) == 2, "Fixed minima and exactly two observations required.")
    first, second = gate["samples"]
    validate_sample(first); validate_sample(second)
    gap = (utc(second["observed_at_utc"]) - utc(first["observed_at_utc"])).total_seconds()
    monotonic = (second["monotonic_ns"] - first["monotonic_ns"]) / 1e9
    need(10 <= gap <= 30 and 10 <= monotonic <= 30 and abs(gap - monotonic) <= 1, "Resource observations require consistent UTC/monotonic 10-30 second intervals.")
    age = (now - utc(second["observed_at_utc"])).total_seconds()
    need(0 <= age <= 60, "Resource gate is future-dated or older than 60 seconds.")
    return {"age_seconds": age, "binding": deepcopy(binding)}


def immediate_check(gate, binding, sample, now):
    validated = validate_gate(gate, binding, now)
    validate_sample(sample)
    age = (time_now(now) - utc(sample["observed_at_utc"])).total_seconds()
    second = gate["samples"][-1]
    wall_delta = (utc(sample["observed_at_utc"]) - utc(second["observed_at_utc"])).total_seconds()
    monotonic_delta = (sample["monotonic_ns"] - second["monotonic_ns"]) / 1e9
    need(0 <= age <= 2 and wall_delta >= 0 and monotonic_delta >= 0 and abs(wall_delta - monotonic_delta) <= 1,
         "Immediate bootstrap sample is stale, future-dated or inconsistent with the prospective gate.")
    return {**validated, "immediate_sample": deepcopy(sample), "checked_before_original_import_and_key": True}


def collect_gate(runtime, binding):
    first = runtime.memory_sample()
    runtime.sleep(10.1)
    second = runtime.memory_sample()
    return {"schema_version": "ap2-hp-native-resource-gate/1", "binding": deepcopy(binding),
            "minimums": dict(MINIMUMS), "samples": [first, second]}


def publish(path, value):
    raw = encoded(value)
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    with pending.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    os.link(pending, path)  # Atomic exclusive publication; pending bytes remain evidence.


class GroupRun:
    """Retain live authority on failures; caller must settle before disposing."""
    def __init__(self, runtime, plan):
        self.runtime, self.plan, self.owners = runtime, deepcopy(plan), []
        self.report = {"schema_version": "ap2-hp-owned-group/1", "status": "preparing", "services": [], "cleanup": [],
                       "native_qualification_established": False, "aggregate_task_grade": None}

    def stop(self):
        cleanup, remaining = [], []
        for role, owner in reversed(self.owners):
            try:
                item = self.runtime.stop_owned(owner)
                qualified = item.get("handles_closed") is True and (item.get("job_empty_observed") is True or item.get("process_created") is False or item.get("launch_attempted") is False) and item.get("errors") == []
            except BaseException as error:
                item, qualified = {"error_type": type(error).__name__, "authority_retained": True}, False
            cleanup.append({"role": role, **item})
            if not qualified:
                remaining.append((role, owner))
        self.owners = list(reversed(remaining))
        self.report["cleanup"].extend(cleanup)
        self.report["live_authority_retained"] = bool(self.owners)
        return not self.owners


def start_group(plan, runtime):
    """Concrete start sequencing using a runtime with task-owned launch methods.

    On readiness success the returned GroupRun retains all live owner handles.
    On any error all retained owners are settled; a cleanup failure returns live
    authority explicitly and cannot become a completed or native result.
    """
    group = GroupRun(runtime, plan)
    allocated = False
    try:
        group.report["validated_inputs"] = validate_plan(plan, runtime.now())
        runtime.bind_plan(deepcopy(plan))
        output = Path(plan["output_root"])
        need(not output.exists(), "Once-only group output allocation is consumed.")
        output.mkdir()
        allocated = True
        publish(output / "plan.json", plan)
        gate = collect_gate(runtime, launch_binding(plan, "group"))
        publish(output / "group-prelaunch.json", gate)
        immediate_check(gate, launch_binding(plan, "group"), runtime.memory_sample(), runtime.now())
        need(runtime.occupied_ports([8001, 8002, 8003]) == [], "An original service port is occupied; no listener may be killed or remapped.")
        (output / ".temp-db").mkdir()
        (output / ".logs").mkdir()
        (output / "services").mkdir()
        for service in SERVICES:
            validate_plan(plan, runtime.now())
            binding = launch_binding(plan, service["role"])
            service_root = output / "services" / service["role"]
            service_root.mkdir()
            gate = collect_gate(runtime, binding)
            publish(service_root / "prelaunch.json", gate)
            immediate_check(gate, binding, runtime.memory_sample(), runtime.now())
            need(runtime.occupied_ports([service["port"]]) == [], "An original service port was occupied before its owned launch.")
            owner = runtime.make_owner(service, service_root)
            group.owners.append((service["role"], owner))
            runtime.launch_bootstrap(owner, plan, service, service_root)
            ready = runtime.wait_original_readiness(owner, plan, service, service_root)
            need(isinstance(ready, dict) and ready.get("owned_connected_original_card") is True and ready.get("binding") == binding,
                 "Distinct source-bound original readiness and connected-peer ownership were not established.")
            group.report["services"].append({"role": service["role"], "readiness": ready})
        group.report["status"] = "owned_original_services_ready_without_case_execution"
        group.report["live_authority_retained"] = True
    except BaseException as error:
        group.report.update(status="refused_or_partial_owned_start", error_type=type(error).__name__, reason=str(error))
        group.stop()
        if group.owners:
            group.report["status"] = "cleanup_incomplete_authority_retained"
    if allocated:
        try:
            publish(Path(plan["output_root"]) / "start-result.json", group.report)
        except BaseException as error:
            group.report.update(status="start_result_publication_failed", publication_error_type=type(error).__name__)
            group.stop()
            if group.owners:
                group.report["status"] = "cleanup_incomplete_authority_retained"
    return group
