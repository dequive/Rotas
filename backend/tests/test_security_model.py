import copy
import json
from pathlib import Path

import pytest

from scripts.validate_security_model import SecurityModelError, validate_security_model

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "infra" / "security" / "ROTAS_SECURITY_MODEL.json"


def _write_model(tmp_path: Path, mutation) -> Path:
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(model)
    mutation(changed)
    path = tmp_path / "security-model.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    return path


def test_canonical_security_model_is_versioned_and_fail_closed():
    assert validate_security_model(REPO_ROOT) == {
        "threats": 16,
        "open_release_blockers": 16,
        "privacy_classes": 4,
        "privacy_flows": 8,
    }


def test_risk_score_and_label_are_recomputed(tmp_path: Path):
    path = _write_model(
        tmp_path,
        lambda model: model["threats"][0].update({"risk_score": 5, "risk": "low"}),
    )
    with pytest.raises(SecurityModelError, match=r"risk_score.*likelihood"):
        validate_security_model(REPO_ROOT, path)


def test_saas_hierarchy_cannot_collapse_tenant_customer_into_tenant(tmp_path: Path):
    path = _write_model(
        tmp_path,
        lambda model: model["multi_tenant_model"].update(
            {"tenant_customer": "another ROTAS tenant"}
        ),
    )
    with pytest.raises(SecurityModelError, match="hierarchy changed"):
        validate_security_model(REPO_ROOT, path)


def test_required_boundary_and_privacy_flow_cannot_disappear(tmp_path: Path):
    def mutate(model):
        model["trust_boundaries"].remove("postgres_rls")
        model["privacy"]["data_flows"] = model["privacy"]["data_flows"][:-1]

    path = _write_model(tmp_path, mutate)
    with pytest.raises(SecurityModelError, match="trust boundaries missing"):
        validate_security_model(REPO_ROOT, path)


def test_baseline_cannot_claim_pentest_or_preclose_threat(tmp_path: Path):
    def mutate(model):
        model["pentest"]["status"] = "passed"
        model["threats"][0]["status"] = "closed"

    path = _write_model(tmp_path, mutate)
    with pytest.raises(SecurityModelError, match="cannot pre-close"):
        validate_security_model(REPO_ROOT, path)


@pytest.mark.parametrize(
    "secret",
    [
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        "-----BEGIN PRIVATE KEY-----",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_model_rejects_secret_patterns(tmp_path: Path, secret: str):
    path = _write_model(
        tmp_path,
        lambda model: model["privacy"].update({"legal_posture": secret}),
    )
    with pytest.raises(SecurityModelError, match="token or private-key"):
        validate_security_model(REPO_ROOT, path)
