import hashlib
import json
from pathlib import Path

from scripts.dr_certification import (
    REQUIRED_EVIDENCE,
    REQUIRED_JOURNEYS,
    evaluate_dr_certification,
)

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_artifact(tmp_path: Path, kind: str) -> dict:
    path = tmp_path / f"{kind}.json"
    path.write_text(
        json.dumps({"kind": kind, "release_sha": RELEASE_SHA}, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "kind": kind,
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "release_sha": RELEASE_SHA,
    }


def _context(tmp_path: Path) -> dict:
    return {
        "schema_version": 1,
        "policy_id": "PR21-DR-CERTIFICATION-V1",
        "environment": "staging",
        "release_sha": RELEASE_SHA,
        "observed_at": "2026-07-31T10:00:00Z",
        "external_runner": True,
        "operator": "restore-operator",
        "backup_operator": "backup-operator",
        "backup_restore": {
            "release_sha": RELEASE_SHA,
            "source_environment": "staging",
            "representative_volume": True,
            "data_authorized": True,
            "authorization_reference": "AUTH-DR-2026-001",
            "client_side_encrypted": True,
            "restic_read_data_clean": True,
            "manifest_checksum_verified": True,
            "temporary_plaintext_removed": True,
            "snapshot_id": "snapshot-abc123",
            "isolated_target": True,
            "restore_succeeded": True,
            "alembic_check_clean": True,
            "tenant_tables": 113,
            "force_rls_tables": 113,
            "unbalanced_journal_entries": 0,
            "journeys_passed": sorted(REQUIRED_JOURNEYS),
            "governance_restored": True,
            "observability_restored": True,
            "cleanup_completed": True,
        },
        "pitr": {
            "wal_archiving_continuous": True,
            "archive_errors": 0,
            "restore_point_created": True,
            "restore_point_reached": True,
            "target_time": "2026-07-31T08:00:00Z",
            "restored_time": "2026-07-31T08:05:00Z",
            "data_loss_seconds": 300,
            "timeline_verified": True,
            "pitr_restore_succeeded": True,
        },
        "cross_region": {
            "primary_region": "af-south-primary",
            "replica_region": "eu-west-replica",
            "separate_failure_domain": True,
            "replica_encrypted": True,
            "versioning_enabled": True,
            "object_lock_verified": True,
            "object_lock_days": 30,
            "replication_lag_seconds": 120,
            "restore_credentials_separated": True,
            "primary_unavailable_simulated": True,
            "restored_from_replica": True,
        },
        "rpo_rto": {
            "measured_rpo_minutes": 5,
            "measured_rto_minutes": 60,
            "started_at": "2026-07-31T08:00:00Z",
            "recovered_at": "2026-07-31T09:00:00Z",
            "full_recovery_timed": True,
            "representative_load": True,
            "restored_bytes": 10_000_000_000,
            "independent_operator_observed": True,
            "incident_paging_exercised": True,
        },
        "evidence": {
            group: [_write_artifact(tmp_path, kind) for kind in sorted(kinds)]
            for group, kinds in REQUIRED_EVIDENCE.items()
        },
    }


def test_dr_certification_passes_complete_bundle(tmp_path):
    result = evaluate_dr_certification(_context(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "backup_restore": True,
        "pitr": True,
        "cross_region": True,
        "rpo_rto": True,
    }
    assert result["evidence_files"] == 11
    assert result["blockers"] == []


def test_dr_certification_rejects_each_runtime_control(tmp_path):
    context = _context(tmp_path)
    context["backup_restore"]["force_rls_tables"] = 112
    context["pitr"]["data_loss_seconds"] = 901
    context["cross_region"]["replica_region"] = "af-south-primary"
    context["rpo_rto"]["measured_rto_minutes"] = 241

    result = evaluate_dr_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert result["controls"] == {
        "backup_restore": False,
        "pitr": False,
        "cross_region": False,
        "rpo_rto": False,
    }


def test_dr_certification_rejects_evidence_drift(tmp_path):
    context = _context(tmp_path)
    context["evidence"]["backup_restore"][0]["sha256"] = "0" * 64
    context["evidence"]["pitr"].append(context["evidence"]["pitr"][0].copy())
    report_path = tmp_path / context["evidence"]["cross_region"][0]["path"]
    physical = json.loads(report_path.read_text(encoding="utf-8"))
    physical["release_sha"] = "f" * 40
    report_path.write_text(json.dumps(physical, sort_keys=True), encoding="utf-8")
    context["evidence"]["cross_region"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()

    result = evaluate_dr_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "evidence.backup_restore[0] hash mismatch" in blockers
    assert "evidence.pitr duplicate kind" in blockers
    assert "physical release SHA mismatch" in blockers


def test_dr_certification_rejects_rto_timestamp_drift_and_bad_journey_set(tmp_path):
    context = _context(tmp_path)
    context["rpo_rto"]["measured_rto_minutes"] = 30
    context["backup_restore"]["journeys_passed"] = ["authentication"]

    result = evaluate_dr_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "measured duration does not match timestamps" in blockers
    assert "journeys_passed set mismatch" in blockers


def test_dr_certification_global_drift_makes_all_controls_false(tmp_path):
    context = _context(tmp_path)
    context["operator"] = context["backup_operator"]

    result = evaluate_dr_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())
