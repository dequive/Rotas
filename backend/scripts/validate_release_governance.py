"""Validate the versioned PR-00 release-governance contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROLES = {"TL", "BE", "FE-M", "FE-D", "QA", "SEC", "SRE", "PO"}
BRANCHES = {"master", "main", "stabilization/**"}
CHECKS = {"Backend", "Frontend", "E2E"}
CHANGE_CLASSES = {"gate_fix", "security_fix", "release_blocker"}
CODEOWNER_PATTERNS = {
    "*",
    "/.github/",
    "/backend/",
    "/apps/manager/",
    "/apps/driver/",
    "/infra/",
    "/docs/",
}
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


def _entries(path: Path) -> dict[str, set[str]]:
    entries: dict[str, set[str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            entries[fields[0]] = {
                owner.removeprefix("@") for owner in fields[1:]
            }
    return entries


def evaluate(policy: object, *, repo_root: Path) -> dict:
    blockers: list[str] = []
    if not isinstance(policy, dict):
        return {"decision": "INVALID", "blockers": ["policy must be an object"]}
    if policy.get("schema_version") != 1:
        blockers.append("schema_version must be 1")
    if policy.get("policy_id") != "PR00-RELEASE-GOVERNANCE-V1":
        blockers.append("policy_id contains drift")
    if policy.get("repository") != "dequive/Rotas":
        blockers.append("repository contains drift")

    owners = policy.get("owners")
    logins: set[str] = set()
    if not isinstance(owners, dict) or set(owners) != ROLES:
        blockers.append("owners must contain exactly the eight Sprint 0 roles")
    else:
        for role, login in owners.items():
            if not isinstance(login, str) or not LOGIN.fullmatch(login):
                blockers.append(f"owners.{role} must be a valid GitHub login")
            else:
                logins.add(login)

    freeze = policy.get("feature_freeze")
    if not isinstance(freeze, dict) or freeze.get("active") is not True:
        blockers.append("feature freeze must be active")
    elif set(freeze.get("allowed_change_classes", [])) != CHANGE_CLASSES:
        blockers.append("feature freeze change classes contain drift")

    branch = policy.get("branch_policy")
    if not isinstance(branch, dict):
        blockers.append("branch policy is required")
    else:
        if set(branch.get("target_patterns", [])) != BRANCHES:
            blockers.append("branch targets contain drift")
        if branch.get("direct_pushes_allowed") is not False:
            blockers.append("direct pushes must be disabled")
        for field in (
            "pull_request_required",
            "dismiss_stale_reviews",
            "code_owner_review_required",
            "conversation_resolution_required",
        ):
            if branch.get(field) is not True:
                blockers.append(f"branch_policy.{field} must be true")
        approvals = branch.get("required_approvals")
        if not isinstance(approvals, int) or isinstance(approvals, bool) or approvals < 2:
            blockers.append("at least two approvals are required")
        if set(branch.get("required_status_checks", [])) != CHECKS:
            blockers.append("required status checks contain drift")

    candidate = policy.get("release_candidate")
    if not isinstance(candidate, dict) or any(
        candidate.get(field) is not True
        for field in (
            "clean_tree_required",
            "full_git_sha_required",
            "remote_ci_required",
            "same_sha_for_all_gates",
        )
    ):
        blockers.append("release candidate requirements are incomplete")

    try:
        codeowners = _entries(repo_root / ".github" / "CODEOWNERS")
    except OSError as exc:
        blockers.append(f"cannot read CODEOWNERS: {exc}")
        codeowners = {}
    for pattern in CODEOWNER_PATTERNS:
        mapped = codeowners.get(pattern, set())
        if not mapped or not mapped.issubset(logins):
            blockers.append(f"CODEOWNERS pattern {pattern} is not accountable")

    return {
        "schema_version": 1,
        "gate": "PR-00",
        "decision": "VALID" if not blockers else "INVALID",
        "roles": len(owners) if isinstance(owners, dict) else 0,
        "distinct_owners": len(logins),
        "blockers": blockers,
        "note": "Validity does not prove that GitHub branch protection is applied.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        result = evaluate(policy, repo_root=args.repo_root.resolve())
    except (OSError, json.JSONDecodeError) as exc:
        result = {"gate": "PR-00", "decision": "INVALID", "blockers": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
