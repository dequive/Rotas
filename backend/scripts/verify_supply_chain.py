"""Validate cryptographic supply-chain evidence for the four ROTAS images."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.validate_staging_manifest import (
    CUSTOM_IMAGE_KEYS,
    IMMUTABLE_IMAGE,
    RELEASE_SHA,
)

FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
POLICY_ID = "PR19-SUPPLY-CHAIN-V1"
SBOM_PREDICATE = "https://spdx.dev/Document"
PROVENANCE_PREDICATE = "https://slsa.dev/provenance/v1"
REQUIRED_EVIDENCE_KINDS = {
    "signature",
    "sbom",
    "provenance",
    "scanner",
    "admission",
}


class SupplyChainBundleError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)


def _subject_digest(reference: str) -> str:
    if not IMMUTABLE_IMAGE.fullmatch(reference):
        return ""
    return reference.rsplit("@", 1)[1]


def _require_verified_subject(
    *,
    image_key: str,
    section_name: str,
    section: object,
    subject_digest: str,
    blockers: list[str],
) -> dict[str, Any]:
    if not isinstance(section, dict):
        blockers.append(f"{image_key}: {section_name} evidence is missing.")
        return {}
    if section.get("verified") is not True:
        blockers.append(f"{image_key}: {section_name} is not verified.")
    if section.get("subject_digest") != subject_digest:
        blockers.append(f"{image_key}: {section_name} subject digest mismatch.")
    return section


def evaluate_supply_chain_bundle(
    bundle: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(bundle, dict):
        raise SupplyChainBundleError("Supply-chain bundle must be an object.")
    if bundle.get("schema_version") != 1:
        blockers.append("schema_version must be 1.")
    if bundle.get("policy_id") != POLICY_ID:
        blockers.append(f"policy_id must be {POLICY_ID}.")

    release_sha = str(bundle.get("release_sha", ""))
    if not RELEASE_SHA.fullmatch(release_sha):
        blockers.append("release_sha must be a full lowercase Git SHA.")
    elif release_sha == "0" * 40:
        blockers.append("release_sha must not be the template placeholder.")
    repository = str(bundle.get("source_repository", ""))
    if not _https_url(repository):
        blockers.append("source_repository must be an HTTPS URL.")
    elif "REPLACE" in repository or repository.endswith(".invalid"):
        blockers.append("source_repository must not be a template placeholder.")
    expected_identity = str(bundle.get("expected_certificate_identity", "")).strip()
    if not expected_identity:
        blockers.append("expected_certificate_identity is required.")
    elif "REPLACE" in expected_identity:
        blockers.append("expected_certificate_identity must not be a template placeholder.")
    expected_issuer = str(bundle.get("expected_oidc_issuer", ""))
    if not _https_url(expected_issuer):
        blockers.append("expected_oidc_issuer must be an HTTPS URL.")

    images = bundle.get("images")
    if not isinstance(images, dict) or set(images) != set(CUSTOM_IMAGE_KEYS):
        blockers.append("images must contain exactly the four ROTAS application images.")
        images = {}

    references: set[str] = set()
    evidence_files = 0
    for image_key in sorted(CUSTOM_IMAGE_KEYS):
        image = images.get(image_key)
        if not isinstance(image, dict):
            blockers.append(f"{image_key}: image evidence is missing.")
            continue
        reference = str(image.get("reference", ""))
        subject_digest = _subject_digest(reference)
        if not subject_digest:
            blockers.append(f"{image_key}: reference must be an immutable RepoDigest.")
        elif ".invalid/" in reference or subject_digest == "sha256:" + ("0" * 64):
            blockers.append(f"{image_key}: reference must not be a template placeholder.")
        elif reference in references:
            blockers.append(f"{image_key}: image reference must be unique.")
        references.add(reference)

        signature = _require_verified_subject(
            image_key=image_key,
            section_name="signature",
            section=image.get("signature"),
            subject_digest=subject_digest,
            blockers=blockers,
        )
        if signature.get("certificate_identity") != expected_identity:
            blockers.append(f"{image_key}: certificate identity mismatch.")
        if signature.get("oidc_issuer") != expected_issuer:
            blockers.append(f"{image_key}: OIDC issuer mismatch.")
        if signature.get("transparency_log_verified") is not True:
            blockers.append(f"{image_key}: transparency log is not verified.")

        sbom = _require_verified_subject(
            image_key=image_key,
            section_name="SBOM attestation",
            section=image.get("sbom"),
            subject_digest=subject_digest,
            blockers=blockers,
        )
        if sbom.get("predicate_type") != SBOM_PREDICATE:
            blockers.append(f"{image_key}: SBOM predicate type mismatch.")

        provenance = _require_verified_subject(
            image_key=image_key,
            section_name="provenance attestation",
            section=image.get("provenance"),
            subject_digest=subject_digest,
            blockers=blockers,
        )
        if provenance.get("predicate_type") != PROVENANCE_PREDICATE:
            blockers.append(f"{image_key}: provenance predicate type mismatch.")
        if provenance.get("source_repository") != repository:
            blockers.append(f"{image_key}: provenance source repository mismatch.")
        if provenance.get("source_revision") != release_sha:
            blockers.append(f"{image_key}: provenance source revision mismatch.")
        if not str(provenance.get("builder_id", "")).strip():
            blockers.append(f"{image_key}: provenance builder_id is required.")
        if provenance.get("mode") != "max":
            blockers.append(f"{image_key}: provenance mode must be max.")

        scanner = _require_verified_subject(
            image_key=image_key,
            section_name="scanner report",
            section=image.get("scanner"),
            subject_digest=subject_digest,
            blockers=blockers,
        )
        if scanner.get("critical") != 0 or scanner.get("high") != 0:
            blockers.append(f"{image_key}: scanner must report zero high/critical.")
        if scanner.get("database_fresh") is not True:
            blockers.append(f"{image_key}: scanner database freshness is not proven.")

        admission = image.get("admission")
        if not isinstance(admission, dict):
            blockers.append(f"{image_key}: admission evidence is missing.")
        else:
            if admission.get("policy_enforced") is not True:
                blockers.append(f"{image_key}: signature admission policy is not enforced.")
            if admission.get("digest_allowed") is not True:
                blockers.append(f"{image_key}: digest was not admitted by policy.")
            if admission.get("subject_digest") != subject_digest:
                blockers.append(f"{image_key}: admission subject digest mismatch.")

        evidence = image.get("evidence")
        if not isinstance(evidence, list):
            blockers.append(f"{image_key}: hashed evidence files are required.")
            evidence = []
        observed_kinds: set[str] = set()
        observed_paths: set[str] = set()
        for index, artifact in enumerate(evidence):
            if not isinstance(artifact, dict):
                blockers.append(f"{image_key}: evidence {index} must be an object.")
                continue
            kind = str(artifact.get("kind", ""))
            if kind in observed_kinds:
                blockers.append(f"{image_key}: duplicate evidence kind: {kind}.")
            observed_kinds.add(kind)
            relative_path = artifact.get("path")
            expected_hash = str(artifact.get("sha256", ""))
            if artifact.get("release_sha") != release_sha:
                blockers.append(f"{image_key}: evidence {index} release SHA mismatch.")
            if not isinstance(relative_path, str) or not relative_path:
                blockers.append(f"{image_key}: evidence {index} path is required.")
                continue
            if relative_path in observed_paths:
                blockers.append(f"{image_key}: duplicate evidence path: {relative_path}.")
            observed_paths.add(relative_path)
            if not FILE_SHA256.fullmatch(expected_hash):
                blockers.append(f"{image_key}: evidence {index} SHA-256 is invalid.")
                continue
            path = Path(relative_path)
            if not path.is_absolute():
                path = base_dir / path
            try:
                actual_hash = sha256_file(path)
            except OSError as exc:
                blockers.append(f"{image_key}: cannot read evidence {index}: {exc}.")
                continue
            if actual_hash != expected_hash:
                blockers.append(f"{image_key}: evidence {index} hash mismatch.")
                continue
            evidence_files += 1
        if observed_kinds != REQUIRED_EVIDENCE_KINDS:
            blockers.append(f"{image_key}: evidence kinds are incomplete or contain drift.")

    passed = not blockers
    return {
        "schema_version": 1,
        "artifact_type": "release_evidence_fragment",
        "policy_id": POLICY_ID,
        "release_sha": release_sha,
        "passed": passed,
        "decision": "PASS" if passed else "NO-GO",
        "images": len(images),
        "evidence_files": evidence_files,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        bundle_path = args.bundle.resolve()
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        result = evaluate_supply_chain_bundle(bundle, base_dir=bundle_path.parent)
    except (OSError, json.JSONDecodeError, SupplyChainBundleError) as exc:
        result = {
            "schema_version": 1,
            "artifact_type": "release_evidence_fragment",
            "policy_id": POLICY_ID,
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
