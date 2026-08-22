import hashlib
from pathlib import Path

from scripts.release_gate import (
    REQUIRED_CONTROLS,
    REQUIRED_SIGNOFFS,
    evaluate_release_gate,
)

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _manifest(tmp_path: Path) -> dict:
    workstreams = {}
    for index, pr_id in enumerate(REQUIRED_CONTROLS, 18):
        evidence = tmp_path / f"{pr_id}.json"
        evidence.write_text(f'{{"pr":"{pr_id}","release_sha":"{RELEASE_SHA}"}}', encoding="utf-8")
        digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
        evidence_digest = hashlib.sha256(digest.encode("ascii")).hexdigest()
        workstreams[pr_id] = {
            "controls": {control: True for control in REQUIRED_CONTROLS[pr_id]},
            "evidence": [
                {
                    "path": evidence.name,
                    "sha256": digest,
                    "release_sha": RELEASE_SHA,
                }
            ],
            "signoffs": [
                {
                    "role": role,
                    "approver": f"approver-{index}-{role}",
                    "approved": True,
                    "release_sha": RELEASE_SHA,
                    "evidence_digest": evidence_digest,
                    "signed_at": "2026-07-30T10:00:00Z",
                }
                for role in REQUIRED_SIGNOFFS[pr_id]
            ],
        }
    return {
        "schema_version": 1,
        "release_sha": RELEASE_SHA,
        "requested_decision": "GO",
        "workstreams": workstreams,
    }


def test_release_gate_returns_go_only_for_complete_hashed_evidence(tmp_path):
    result = evaluate_release_gate(_manifest(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "GO"
    assert result["workstreams"] == 8
    assert result["evidence_files"] == 8
    assert result["signoffs"] == sum(map(len, REQUIRED_SIGNOFFS.values()))
    assert result["blockers"] == []


def test_release_gate_returns_no_go_for_red_control_hash_drift_and_signoff_gap(
    tmp_path,
):
    manifest = _manifest(tmp_path)
    manifest["workstreams"]["PR-18"]["controls"]["no_unwaived_high_critical"] = False
    manifest["workstreams"]["PR-22"]["evidence"][0]["sha256"] = "0" * 64
    manifest["workstreams"]["PR-25"]["signoffs"] = []

    result = evaluate_release_gate(manifest, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "PR-18: control is not green" in blockers
    assert "PR-22: evidence 0 hash mismatch" in blockers
    assert "PR-25: required signoff roles are incomplete" in blockers


def test_release_gate_rejects_partial_workstream_set(tmp_path):
    manifest = _manifest(tmp_path)
    del manifest["workstreams"]["PR-23"]

    result = evaluate_release_gate(manifest, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert "workstreams must contain exactly PR-18 through PR-25." in result["blockers"]
