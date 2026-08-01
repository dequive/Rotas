import json
import re
from copy import deepcopy
from pathlib import Path

from scripts.validate_release_governance import evaluate

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "infra" / "release" / "PR00_RELEASE_GOVERNANCE.json"


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_repository_governance_contract_is_valid():
    result = evaluate(_policy(), repo_root=ROOT)

    assert result["decision"] == "VALID"
    assert result["roles"] == 8
    assert result["distinct_owners"] == 1
    assert result["blockers"] == []


def test_contract_rejects_missing_role_and_weak_policy():
    policy = deepcopy(_policy())
    del policy["owners"]["SEC"]
    policy["branch_policy"]["required_approvals"] = 1
    policy["branch_policy"]["direct_pushes_allowed"] = True

    result = evaluate(policy, repo_root=ROOT)
    blockers = " ".join(result["blockers"])

    assert result["decision"] == "INVALID"
    assert "exactly the eight Sprint 0 roles" in blockers
    assert "at least two approvals" in blockers
    assert "direct pushes must be disabled" in blockers


def test_contract_rejects_missing_codeowner_scope(tmp_path):
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.parent.mkdir(parents=True)
    codeowners.write_text("* @dequive\n", encoding="utf-8")

    result = evaluate(_policy(), repo_root=tmp_path)

    assert result["decision"] == "INVALID"
    assert any("/.github/" in blocker for blocker in result["blockers"])


def test_ci_enforces_contract_on_stabilization_branches():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert '"stabilization/**"' in workflow
    assert "Validate PR-00 release governance contract" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "ROTAS_ALLOW_DEMO_FALLBACK" not in workflow
    assert "postgres:16@sha256:" in workflow
    assert "redis:7@sha256:" in workflow
    assert "npm --workspace apps/manager run test" in workflow
    assert "npm --workspace apps/driver run test" in workflow
    action_refs = re.findall(r"uses:\s+actions/[^@\s]+@([^\s]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)
