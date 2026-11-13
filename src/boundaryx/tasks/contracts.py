from pathlib import Path
from typing import Any
from boundaryx.core.evidence import EvidenceError, read, verify_manifest


def check_review(review: dict[str, Any], definition_hash: str | None = None) -> None:
    reviewer, reasoning = review.get("reviewer"), review.get("reasoning")
    if (review.get("decision") != "approve" or not isinstance(reviewer, str) or not reviewer.strip()
            or not isinstance(reasoning, str) or not reasoning.strip()):
        raise EvidenceError("Pending Human Review: gold is provisional")
    if definition_hash is not None and review.get("reviewed_definition_sha256") != definition_hash:
        raise EvidenceError("Review does not bind the frozen definition/gold hash")


def check_team_reviews(entry: dict[str, Any], definition_hash: str) -> None:
    reviews = entry["reviews"]
    if len(reviews) < 2:
        raise EvidenceError("Two independent teammate reviews are required")
    names = []
    for review in reviews:
        check_review(review, definition_hash)
        names.append(review["reviewer"].strip().casefold())
    if len(set(names)) != len(names):
        raise EvidenceError("The same named reviewer cannot supply both independent reviews")
    if entry.get("disagreement") and not entry.get("resolution"):
        raise EvidenceError("A recorded disagreement requires an explicit resolution")


def heldout_status(root: Path) -> dict[str, Any]:
    count = verify_manifest(root)
    tasks = read(root / "tasks.json")["tasks"]
    reviews = read(root / "review-decisions.json")
    definition_hash = read(root / "freeze.json")["tasks_sha256"]
    eligible = []
    for task in tasks:
        entry = reviews["tasks"][task["id"]]
        try:
            check_team_reviews(entry, definition_hash)
            eligible.append(task["id"])
        except EvidenceError:
            pass
    return {"status": "Pending Human Review" if len(eligible) != len(tasks) else "Completed",
            "frozen_files_verified": count, "task_instances": len(tasks), "eligible": eligible,
            "gold_status": "provisional until two distinct named teammate reviewers approve the frozen definitions",
            "supervisor_role": "progress_observer",
            "supervisor_approval_required": False,
            "evaluations": 0}
