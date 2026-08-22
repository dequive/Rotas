import hashlib
import json
from pathlib import Path

from scripts.staging_certification import (
    REQUIRED_EVIDENCE,
    evaluate_staging_certification,
)
from scripts.validate_staging_manifest import REQUIRED_SECRET_FILES

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_artifact(tmp_path: Path, kind: str, payload: dict) -> dict:
    safe_name = kind.replace(":", "-")
    path = tmp_path / f"{safe_name}.json"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return {
        "kind": kind,
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "release_sha": RELEASE_SHA,
    }


def _context(tmp_path: Path) -> dict:
    supply_result = {
        "passed": True,
        "policy_id": "PR19-SUPPLY-CHAIN-V1",
        "release_sha": RELEASE_SHA,
        "images": 4,
        "evidence_files": 20,
    }
    evidence = {}
    for group, kinds in REQUIRED_EVIDENCE.items():
        evidence[group] = [
            _write_artifact(
                tmp_path,
                kind,
                supply_result if kind == "supply_chain_result" else {"kind": kind},
            )
            for kind in sorted(kinds)
        ]
    tls = {
        host: {
            "url": f"https://{host}.staging.rotas.example.com",
            "chain_verified": True,
            "hostname_verified": True,
            "protocol": "TLSv1.3",
            "not_before": "2026-07-01T00:00:00Z",
            "not_after": "2026-10-31T00:00:00Z",
            "hsts_max_age": 31_536_000,
            "hsts_include_subdomains": True,
        }
        for host in ("manager", "driver", "api", "grafana")
    }
    migrations = {
        "rotas": {
            "release_sha": RELEASE_SHA,
            "one_shot": True,
            "exit_code": 0,
            "head": "rec13",
            "started_at": "2026-07-31T08:00:00Z",
            "finished_at": "2026-07-31T08:01:00Z",
            "alembic_check_clean": True,
        },
        "governance": {
            "release_sha": RELEASE_SHA,
            "one_shot": True,
            "exit_code": 0,
            "head": "0002",
            "started_at": "2026-07-31T08:00:00Z",
            "finished_at": "2026-07-31T08:01:30Z",
        },
    }
    return {
        "schema_version": 1,
        "policy_id": "PR19-STAGING-CERTIFICATION-V1",
        "environment": "staging",
        "release_sha": RELEASE_SHA,
        "observed_at": "2026-07-31T09:00:00Z",
        "external_runner": True,
        "operator": "sre-independent",
        "supply_chain": supply_result,
        "tls": tls,
        "external_secrets": {
            "provider": "approved-secret-manager",
            "secret_count": len(REQUIRED_SECRET_FILES),
            "injected_as_files": True,
            "runtime_environment_values_absent": True,
            "repository_scan_clean": True,
            "temporary_material_removed": True,
        },
        "migrations": migrations,
        "runtime": {
            "release_sha": RELEASE_SHA,
            "version_endpoint_sha": RELEASE_SHA,
            "health_deep": "healthy",
            "database_role": "rotas_app",
            "database_superuser": False,
            "database_bypass_rls": False,
            "worker_heartbeat": True,
            "applications_started_at": "2026-07-31T08:02:00Z",
        },
        "evidence": evidence,
    }


def test_staging_certification_passes_complete_runtime_bundle(tmp_path):
    result = evaluate_staging_certification(_context(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "immutable_images": True,
        "tls": True,
        "external_secrets": True,
        "migrations": True,
    }
    assert result["evidence_files"] == 9
    assert result["blockers"] == []


def test_staging_certification_rejects_runtime_control_failures(tmp_path):
    context = _context(tmp_path)
    context["supply_chain"]["passed"] = False
    context["tls"]["api"]["chain_verified"] = False
    context["external_secrets"]["runtime_environment_values_absent"] = False
    context["migrations"]["rotas"]["exit_code"] = 1
    context["runtime"]["database_role"] = "postgres"

    result = evaluate_staging_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "supply_chain.passed mismatch" in blockers
    assert "certificate chain is not verified" in blockers
    assert "runtime_environment_values_absent mismatch" in blockers
    assert "one-shot execution failed" in blockers
    assert "runtime.database_role mismatch" in blockers


def test_staging_certification_rejects_hash_drift_and_missing_evidence_kind(tmp_path):
    context = _context(tmp_path)
    context["evidence"]["tls"][0]["sha256"] = "0" * 64
    context["evidence"]["migrations"].pop()
    context["evidence"]["runtime"].append(context["evidence"]["runtime"][0].copy())

    result = evaluate_staging_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "evidence.tls[0] hash mismatch" in blockers
    assert "evidence.migrations kinds are incomplete" in blockers
    assert "evidence.runtime duplicate kind" in blockers


def test_staging_certification_rejects_placeholder_and_start_before_migrations(
    tmp_path,
):
    context = _context(tmp_path)
    context["release_sha"] = "0" * 40
    context["runtime"]["applications_started_at"] = "2026-07-31T08:00:30Z"

    result = evaluate_staging_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "release_sha must not be the template placeholder" in blockers
    assert "applications started before migrations completed" in blockers
