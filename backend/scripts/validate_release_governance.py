"""Validate the versioned PR-00 release-governance contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_ROLES = {"TL", "BE", "FE-M", "FE-D", "QA", "SEC", "SRE", "PO"}
REQUIRED_BRANCH_PATTERNS = {"master", "main", "stabilization/**"}
REQUIRED_STATUS_CHECKS = {"Backend", "Frontend", "E2E"}
REQUIRED_CHANGE_CLASSES = {"gate_fix", "security_fix", "release_blocker"}
REQUIRED_CODEOWNER_PATTERNS = {
    "*",
    "/.github/",
    "/backend/",
    "/apps/manager/",
    "/apps/driver/",
    "/infra/",
    "/docs/",
}
GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


class GovernanceContractError(ValueError):
    pass


def _codeowner_entries(path: Path) -> dict[str, set[str]]:
    entries: dict[str, set[str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        entries[fields[0]] = {owner.removeprefix("@") for owner in fields[1:]}
    return entries


def evaluate_release_governance(
    policy: object,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(policy, dict):
        raise GovernanceContractError("Governance policy must be an object.")
    if policy.get("schema_version") != 1:
        blockers.append("schema_version must be 1.")
    if policy.get("policy_id") != "PR00-RELEASE-GOVERNANCE-V1":
        blockers.append("policy_id must be PR00-RELEASE-GOVERNANCE-V1.")
    if policy.get("repository") != "dequive/Rotas":
        blockers.append("repository must be dequive/Rotas.")

    owners = policy.get("owners")
    owner_logins: set[str] = set()
    if not isinstance(owners, dict) or set(owners) != REQUIRED_ROLES:
        blockers.append("owners must contain exactly the eight Sprint 0 roles.")
    else:
        for role, login in owners.items():
            if not isinstance(login, str) or not GITHUB_LOGIN.fullmatch(login):
                blockers.append(f"owners.{role} must be a valid GitHub login.")
                continue
            owner_logins.add(login)

    feature_freeze = policy.get("feature_freeze")
    if not isinstance(feature_freeze, dict):
        blockers.append("feature_freeze must be an object.")
    else:
        if feature_freeze.get("active") is not True:
            blockers.append("feature_freeze.active must be true during P0/P1.")
        if set(feature_freeze.get("allowed_change_classes", [])) != REQUIRED_CHANGE_CLASSES:
            blockers.append("feature_freeze allowed change classes contain drift.")

    branch_policy = policy.get("branch_policy")
    if not isinstance(branch_policy, dict):
        blockers.append("branch_policy must be an object.")
    else:
        if set(branch_policy.get("target_patterns", [])) != REQUIRED_BRANCH_PATTERNS:
            blockers.append("branch_policy target patterns contain drift.")
        required_true = {
            "pull_request_required",
            "dismiss_stale_reviews",
            "code_owner_review_required",
            "conversation_resolution_required",
        }
        for field in required_true:
            if branch_policy.get(field) is not True:
                blockers.append(f"branch_policy.{field} must be true.")
        if branch_policy.get("direct_pushes_allowed") is not False:
            blockers.append("branch_policy.direct_pushes_allowed must be false.")
        approvals = branch_policy.get("required_approvals")
        if not isinstance(approvals, int) or isinstance(approvals, bool) or approvals < 2:
            blockers.append("branch_policy.required_approvals must be at least 2.")
        if set(branch_policy.get("required_status_checks", [])) != REQUIRED_STATUS_CHECKS:
            blockers.append("branch_policy required status checks contain drift.")

    release_candidate = policy.get("release_candidate")
    required_rc_fields = {
        "clean_tree_required",
        "full_git_sha_required",
        "remote_ci_required",
        "same_sha_for_all_gates",
    }
    if not isinstance(release_candidate, dict):
        blockers.append("release_candidate must be an object.")
    else:
        for field in required_rc_fields:
            if release_candidate.get(field) is not True:
                blockers.append(f"release_candidate.{field} must be true.")

    codeowners_path = repo_root / ".github" / "CODEOWNERS"
    try:
        codeowners = _codeowner_entries(codeowners_path)
    except OSError as exc:
        blockers.append(f"cannot read CODEOWNERS: {exc}.")
        codeowners = {}
    for pattern in REQUIRED_CODEOWNER_PATTERNS:
        mapped = codeowners.get(pattern, set())
        if not mapped or not mapped.issubset(owner_logins):
            blockers.append(f"CODEOWNERS pattern {pattern} has no registered PR-00 owner.")

    return {
        "schema_version": 1,
        "gate": "PR-00",
        "policy_id": str(policy.get("policy_id", "")),
        "decision": "VALID" if not blockers else "INVALID",
        "roles": len(owners) if isinstance(owners, dict) else 0,
        "distinct_owners": len(owner_logins),
        "blockers": blockers,
        "note": (
            "Contract validity does not prove that GitHub branch protection is applied."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        result = evaluate_release_governance(policy, repo_root=args.repo_root.resolve())
    except (OSError, json.JSONDecodeError, GovernanceContractError) as exc:
        result = {
            "schema_version": 1,
            "gate": "PR-00",
            "decision": "INVALID",
            "blockers": [str(exc)],
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
