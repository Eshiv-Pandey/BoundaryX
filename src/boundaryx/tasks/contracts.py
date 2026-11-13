from pathlib import Path
from typing import Any
from boundaryx.core.evidence import EvidenceError, read, verify_manifest


def check_review(review: dict[str, Any], supervisor: dict[str, Any], definition_hash: str | None = None) -> None:
    if review.get("decision") != "approve" or not review.get("reviewer") or not review.get("reasoning"):
        raise EvidenceError("Pending Human Review: gold is provisional")
    if supervisor.get("decision") != "approve" or not supervisor.get("reviewer") or not supervisor.get("reasoning"):
        raise EvidenceError("Pending Supervisor Review: evaluation is not eligible")
    if definition_hash is not None and any(r.get("reviewed_definition_sha256") != definition_hash for r in (review, supervisor)):
        raise EvidenceError("Review does not bind the frozen definition/gold hash")


def heldout_status(root: Path) -> dict[str, Any]:
    count = verify_manifest(root)
    tasks = read(root / "tasks.json")["tasks"]
    reviews = read(root / "review-decisions.json")
    definition_hash = read(root / "freeze.json")["tasks_sha256"]
    eligible = []
    for task in tasks:
        entry = reviews["tasks"][task["id"]]
        try:
            if len(entry["reviews"]) < 2:
                raise EvidenceError("Two clarity/consistency reviews are required")
            for review in entry["reviews"]:
                check_review(review, entry["supervisor"], definition_hash)
            eligible.append(task["id"])
        except EvidenceError:
            pass
    return {"status": "Pending Human Review" if len(eligible) != len(tasks) else "Completed",
            "frozen_files_verified": count, "task_instances": len(tasks), "eligible": eligible,
            "gold_status": "provisional until named reviewer and supervisor approve",
            "evaluations": 0}
