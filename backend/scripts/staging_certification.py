"""Fail-closed PR-19 certification bundle for a running staging environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.validate_staging_manifest import CUSTOM_IMAGE_KEYS, REQUIRED_SECRET_FILES
from scripts.verify_supply_chain import POLICY_ID

RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
HOST_KEYS = {"manager", "driver", "api", "grafana"}
MIGRATION_KEYS = {"rotas", "governance"}
REQUIRED_EVIDENCE = {
    "supply_chain": {"supply_chain_result"},
    "tls": {f"tls_probe:{host}" for host in HOST_KEYS},
    "external_secrets": {"secret_manager_report"},
    "migrations": {"migration:rotas", "migration:governance"},
    "runtime": {"runtime_report"},
}
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class StagingCertificationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _validate_evidence(
    evidence: object,
    *,
    base_dir: Path,
    release_sha: str,
    blockers: list[str],
) -> tuple[int, dict[str, Path]]:
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_EVIDENCE):
        blockers.append("evidence must contain exactly the five PR-19 evidence groups.")
        return 0, {}
    count = 0
    resolved: dict[str, Path] = {}
    all_paths: set[str] = set()
    for group, required_kinds in REQUIRED_EVIDENCE.items():
        artifacts = evidence.get(group)
        if not isinstance(artifacts, list):
            blockers.append(f"evidence.{group} must be a list.")
            continue
        observed_kinds: set[str] = set()
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                blockers.append(f"evidence.{group}[{index}] must be an object.")
                continue
            kind = str(artifact.get("kind", ""))
            if kind in observed_kinds:
                blockers.append(f"evidence.{group} duplicate kind: {kind}.")
            observed_kinds.add(kind)
            relative_path = artifact.get("path")
            expected_hash = str(artifact.get("sha256", ""))
            if artifact.get("release_sha") != release_sha:
                blockers.append(f"evidence.{group}[{index}] release SHA mismatch.")
            if not isinstance(relative_path, str) or not relative_path:
                blockers.append(f"evidence.{group}[{index}] path is required.")
                continue
            if relative_path in all_paths:
                blockers.append(f"duplicate evidence path: {relative_path}.")
            all_paths.add(relative_path)
            if not FILE_SHA256.fullmatch(expected_hash):
                blockers.append(f"evidence.{group}[{index}] SHA-256 is invalid.")
                continue
            path = Path(relative_path)
            if not path.is_absolute():
                path = base_dir / path
            try:
                actual_hash = sha256_file(path)
            except OSError as exc:
                blockers.append(f"cannot read evidence.{group}[{index}]: {exc}.")
                continue
            if actual_hash != expected_hash:
                blockers.append(f"evidence.{group}[{index}] hash mismatch.")
                continue
            count += 1
            resolved[kind] = path
        if observed_kinds != required_kinds:
            blockers.append(f"evidence.{group} kinds are incomplete or contain drift.")
    return count, resolved


def evaluate_staging_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise StagingCertificationError("Staging certification context must be an object.")
    if context.get("schema_version") != 1:
        blockers.append("schema_version must be 1.")
    if context.get("policy_id") != "PR19-STAGING-CERTIFICATION-V1":
        blockers.append("policy_id must be PR19-STAGING-CERTIFICATION-V1.")
    if context.get("environment") != "staging":
        blockers.append("environment must be staging.")

    release_sha = str(context.get("release_sha", ""))
    if not RELEASE_SHA.fullmatch(release_sha):
        blockers.append("release_sha must be a full lowercase Git SHA.")
    elif release_sha == "0" * 40:
        blockers.append("release_sha must not be the template placeholder.")
    observed_at = _timestamp(context.get("observed_at"))
    if observed_at is None:
        blockers.append("observed_at must be a valid UTC RFC3339 timestamp.")
    if context.get("external_runner") is not True:
        blockers.append("external_runner must be true.")
    if not str(context.get("operator", "")).strip():
        blockers.append("operator is required.")

    evidence_count, evidence_paths = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    supply_chain = context.get("supply_chain")
    if not isinstance(supply_chain, dict):
        blockers.append("supply_chain result is required.")
    else:
        expected = {
            "passed": True,
            "policy_id": POLICY_ID,
            "release_sha": release_sha,
            "images": len(CUSTOM_IMAGE_KEYS),
            "evidence_files": 20,
        }
        for key, value in expected.items():
            if supply_chain.get(key) != value:
                blockers.append(f"supply_chain.{key} mismatch.")
        result_path = evidence_paths.get("supply_chain_result")
        if result_path is not None:
            try:
                physical_result = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                blockers.append(f"cannot parse supply-chain result: {exc}.")
            else:
                for key, value in expected.items():
                    if physical_result.get(key) != value:
                        blockers.append(f"physical supply-chain result {key} mismatch.")

    tls = context.get("tls")
    if not isinstance(tls, dict) or set(tls) != HOST_KEYS:
        blockers.append("tls must contain exactly manager, driver, api and grafana.")
        tls = {}
    tls_hosts: set[str] = set()
    for host_key in sorted(HOST_KEYS):
        probe = tls.get(host_key)
        if not isinstance(probe, dict):
            blockers.append(f"tls.{host_key} probe is required.")
            continue
        url = str(probe.get("url", ""))
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            blockers.append(f"tls.{host_key}.url must be HTTPS.")
        elif parsed.hostname.endswith(".invalid"):
            blockers.append(f"tls.{host_key}.url must not be a placeholder.")
        elif parsed.hostname in tls_hosts:
            blockers.append(f"tls.{host_key}.url hostname must be unique.")
        tls_hosts.add(parsed.hostname or "")
        if probe.get("chain_verified") is not True:
            blockers.append(f"tls.{host_key} certificate chain is not verified.")
        if probe.get("hostname_verified") is not True:
            blockers.append(f"tls.{host_key} hostname is not verified.")
        if probe.get("protocol") not in {"TLSv1.2", "TLSv1.3"}:
            blockers.append(f"tls.{host_key} protocol is not allowed.")
        not_before = _timestamp(probe.get("not_before"))
        not_after = _timestamp(probe.get("not_after"))
        if observed_at is not None and (
            not_before is None
            or not_after is None
            or not_before > observed_at
            or not_after < observed_at + timedelta(days=30)
        ):
            blockers.append(f"tls.{host_key} certificate validity is insufficient.")
        if probe.get("hsts_max_age") is None or not isinstance(
            probe.get("hsts_max_age"), int
        ):
            blockers.append(f"tls.{host_key} HSTS max-age is invalid.")
        elif probe["hsts_max_age"] < 31_536_000:
            blockers.append(f"tls.{host_key} HSTS max-age is too short.")
        if probe.get("hsts_include_subdomains") is not True:
            blockers.append(f"tls.{host_key} HSTS includeSubDomains is required.")

    secrets = context.get("external_secrets")
    if not isinstance(secrets, dict):
        blockers.append("external_secrets result is required.")
    else:
        secret_expectations = {
            "secret_count": len(REQUIRED_SECRET_FILES),
            "injected_as_files": True,
            "runtime_environment_values_absent": True,
            "repository_scan_clean": True,
            "temporary_material_removed": True,
        }
        if not str(secrets.get("provider", "")).strip():
            blockers.append("external_secrets.provider is required.")
        for key, value in secret_expectations.items():
            if secrets.get(key) != value:
                blockers.append(f"external_secrets.{key} mismatch.")

    migrations = context.get("migrations")
    if not isinstance(migrations, dict) or set(migrations) != MIGRATION_KEYS:
        blockers.append("migrations must contain exactly rotas and governance.")
        migrations = {}
    migration_finished: list[datetime] = []
    for migration_key in sorted(MIGRATION_KEYS):
        migration = migrations.get(migration_key)
        if not isinstance(migration, dict):
            blockers.append(f"migrations.{migration_key} result is required.")
            continue
        if migration.get("release_sha") != release_sha:
            blockers.append(f"migrations.{migration_key} release SHA mismatch.")
        if migration.get("one_shot") is not True or migration.get("exit_code") != 0:
            blockers.append(f"migrations.{migration_key} one-shot execution failed.")
        if not str(migration.get("head", "")).strip():
            blockers.append(f"migrations.{migration_key}.head is required.")
        started = _timestamp(migration.get("started_at"))
        finished = _timestamp(migration.get("finished_at"))
        if started is None or finished is None or finished <= started:
            blockers.append(f"migrations.{migration_key} timestamps are invalid.")
        else:
            migration_finished.append(finished)
        if migration_key == "rotas" and migration.get("alembic_check_clean") is not True:
            blockers.append("migrations.rotas Alembic drift check is not clean.")

    runtime = context.get("runtime")
    if not isinstance(runtime, dict):
        blockers.append("runtime result is required.")
    else:
        runtime_expectations = {
            "release_sha": release_sha,
            "version_endpoint_sha": release_sha,
            "health_deep": "healthy",
            "database_role": "rotas_app",
            "database_superuser": False,
            "database_bypass_rls": False,
            "worker_heartbeat": True,
        }
        for key, value in runtime_expectations.items():
            if runtime.get(key) != value:
                blockers.append(f"runtime.{key} mismatch.")
        applications_started_at = _timestamp(runtime.get("applications_started_at"))
        if applications_started_at is None:
            blockers.append("runtime.applications_started_at is invalid.")
        elif migration_finished and applications_started_at <= max(migration_finished):
            blockers.append("applications started before migrations completed.")

    evidence_shape_failed = any(
        blocker.startswith("evidence must contain") for blocker in blockers
    )
    controls = {
        "immutable_images": not evidence_shape_failed
        and not any(
            "supply_chain" in blocker or blocker.startswith("evidence.supply_chain")
            for blocker in blockers
        ),
        "tls": not evidence_shape_failed
        and not any(
            blocker.startswith("tls") or blocker.startswith("evidence.tls")
            for blocker in blockers
        ),
        "external_secrets": not evidence_shape_failed
        and not any(
            blocker.startswith("external_secrets")
            or blocker.startswith("evidence.external_secrets")
            for blocker in blockers
        ),
        "migrations": not evidence_shape_failed
        and not any(
            blocker.startswith("migrations")
            or blocker.startswith("evidence.migrations")
            or blocker.startswith("applications started")
            for blocker in blockers
        ),
    }
    passed = not blockers
    return {
        "schema_version": 1,
        "artifact_type": "release_evidence_fragment",
        "policy_id": "PR19-STAGING-CERTIFICATION-V1",
        "release_sha": release_sha,
        "passed": passed,
        "decision": "PASS" if passed else "NO-GO",
        "controls": controls,
        "evidence_files": evidence_count,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        context_path = args.context.resolve()
        context = json.loads(context_path.read_text(encoding="utf-8"))
        result = evaluate_staging_certification(context, base_dir=context_path.parent)
    except (OSError, json.JSONDecodeError, StagingCertificationError) as exc:
        result = {
            "schema_version": 1,
            "artifact_type": "release_evidence_fragment",
            "policy_id": "PR19-STAGING-CERTIFICATION-V1",
            "passed": False,
            "decision": "NO-GO",
            "blockers": [str(exc)],
        }
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
