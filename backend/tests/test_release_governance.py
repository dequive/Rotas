import json
from copy import deepcopy
from pathlib import Path

from scripts.validate_release_governance import evaluate_release_governance

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "infra" / "release" / "PR00_RELEASE_GOVERNANCE.json"


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_repository_pr00_governance_contract_is_valid():
    result = evaluate_release_governance(_policy(), repo_root=REPO_ROOT)

    assert result["decision"] == "VALID"
    assert result["roles"] == 8
    assert result["distinct_owners"] == 1
    assert result["blockers"] == []


def test_ci_enforces_pr00_contract_on_stabilization_branches():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert '"stabilization/**"' in workflow
    assert "Validate PR-00 release governance contract" in workflow
    assert "scripts.validate_release_governance" in workflow


def test_governance_contract_rejects_missing_role_and_weak_branch_policy():
    policy = deepcopy(_policy())
    del policy["owners"]["SEC"]
    policy["branch_policy"]["required_approvals"] = 1
    policy["branch_policy"]["direct_pushes_allowed"] = True

    result = evaluate_release_governance(policy, repo_root=REPO_ROOT)

    assert result["decision"] == "INVALID"
    blockers = " ".join(result["blockers"])
    assert "exactly the eight Sprint 0 roles" in blockers
    assert "required_approvals must be at least 2" in blockers
    assert "direct_pushes_allowed must be false" in blockers


def test_governance_contract_rejects_missing_codeowner_scope(tmp_path):
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.parent.mkdir(parents=True)
    codeowners.write_text("* @dequive\n", encoding="utf-8")

    result = evaluate_release_governance(_policy(), repo_root=tmp_path)

    assert result["decision"] == "INVALID"
    assert any("/.github/" in blocker for blocker in result["blockers"])
