import hashlib
from pathlib import Path

from scripts.validate_staging_manifest import CUSTOM_IMAGE_KEYS
from scripts.verify_supply_chain import (
    REQUIRED_EVIDENCE_KINDS,
    evaluate_supply_chain_bundle,
)

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"
DIGESTS = {
    image_key: f"sha256:{index:064x}"
    for index, image_key in enumerate(sorted(CUSTOM_IMAGE_KEYS), 1)
}


def _bundle(tmp_path: Path) -> dict:
    images = {}
    for image_key in sorted(CUSTOM_IMAGE_KEYS):
        digest = DIGESTS[image_key]
        evidence = []
        for kind in sorted(REQUIRED_EVIDENCE_KINDS):
            artifact = tmp_path / f"{image_key}-{kind}.json"
            artifact.write_text(
                f'{{"kind":"{kind}","release_sha":"{RELEASE_SHA}"}}',
                encoding="utf-8",
            )
            evidence.append(
                {
                    "kind": kind,
                    "path": artifact.name,
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "release_sha": RELEASE_SHA,
                }
            )
        images[image_key] = {
            "reference": f"registry.example/rotas/{image_key.lower()}@{digest}",
            "signature": {
                "verified": True,
                "subject_digest": digest,
                "certificate_identity": "https://github.com/rotas/release.yml@refs/heads/main",
                "oidc_issuer": "https://token.actions.githubusercontent.com",
                "transparency_log_verified": True,
            },
            "sbom": {
                "verified": True,
                "subject_digest": digest,
                "predicate_type": "https://spdx.dev/Document",
            },
            "provenance": {
                "verified": True,
                "subject_digest": digest,
                "predicate_type": "https://slsa.dev/provenance/v1",
                "source_repository": "https://github.com/rotas/rotas",
                "source_revision": RELEASE_SHA,
                "builder_id": "https://github.com/rotas/release.yml",
                "mode": "max",
            },
            "scanner": {
                "verified": True,
                "subject_digest": digest,
                "critical": 0,
                "high": 0,
                "database_fresh": True,
            },
            "admission": {
                "policy_enforced": True,
                "digest_allowed": True,
                "subject_digest": digest,
            },
            "evidence": evidence,
        }
    return {
        "schema_version": 1,
        "policy_id": "PR19-SUPPLY-CHAIN-V1",
        "release_sha": RELEASE_SHA,
        "source_repository": "https://github.com/rotas/rotas",
        "expected_certificate_identity": (
            "https://github.com/rotas/release.yml@refs/heads/main"
        ),
        "expected_oidc_issuer": "https://token.actions.githubusercontent.com",
        "images": images,
    }


def test_gate_passes_complete_digest_bound_hashed_bundle(tmp_path):
    result = evaluate_supply_chain_bundle(_bundle(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "PASS"
    assert result["images"] == 4
    assert result["evidence_files"] == 20
    assert result["blockers"] == []


def test_gate_rejects_digest_signature_attestation_and_scanner_drift(tmp_path):
    bundle = _bundle(tmp_path)
    image = bundle["images"]["ROTAS_BACKEND_IMAGE"]
    image["signature"]["certificate_identity"] = "untrusted"
    image["sbom"]["subject_digest"] = "sha256:" + ("f" * 64)
    image["provenance"]["source_revision"] = "f" * 40
    image["scanner"]["high"] = 1
    image["admission"]["digest_allowed"] = False

    result = evaluate_supply_chain_bundle(bundle, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "certificate identity mismatch" in blockers
    assert "SBOM attestation subject digest mismatch" in blockers
    assert "provenance source revision mismatch" in blockers
    assert "zero high/critical" in blockers
    assert "digest was not admitted" in blockers


def test_gate_rejects_partial_image_set_and_unhashed_evidence(tmp_path):
    bundle = _bundle(tmp_path)
    del bundle["images"]["ROTAS_DRIVER_IMAGE"]
    bundle["images"]["ROTAS_BACKEND_IMAGE"]["evidence"][0]["sha256"] = "0" * 64

    result = evaluate_supply_chain_bundle(bundle, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert "images must contain exactly" in " ".join(result["blockers"])


def test_gate_rejects_missing_evidence_kind(tmp_path):
    bundle = _bundle(tmp_path)
    bundle["images"]["ROTAS_MANAGER_IMAGE"]["evidence"].pop()

    result = evaluate_supply_chain_bundle(bundle, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert "evidence kinds are incomplete" in " ".join(result["blockers"])


def test_gate_rejects_template_placeholders(tmp_path):
    bundle = _bundle(tmp_path)
    bundle["release_sha"] = "0" * 40
    bundle["source_repository"] = "https://registry.invalid"
    bundle["expected_certificate_identity"] = "REPLACE_WITH_IDENTITY"

    result = evaluate_supply_chain_bundle(bundle, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    blockers = " ".join(result["blockers"])
    assert "release_sha must not be the template placeholder" in blockers
    assert "source_repository must not be a template placeholder" in blockers
    assert "expected_certificate_identity must not be a template placeholder" in blockers
