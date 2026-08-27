import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr18-release-evidence.yml"


def test_pr18_release_workflow_is_sha_bound_and_fail_closed():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in content
    assert "release_sha:" in content
    assert 'ref: ${{ inputs.release_sha }}' in content
    assert '"$RELEASE_SHA" != "$GITHUB_SHA"' in content
    assert 'node-version: "20.20.2"' in content
    assert "npm ci --ignore-scripts" in content
    assert "npm --workspace apps/manager run build" in content
    assert "standalone/node_modules/sharp" in content
    assert "standalone/node_modules/postcss" in content
    assert ".release-evidence/pr18/runtime-surface.json" in content
    assert "--profile release_candidate" in content
    assert '--release-sha "$RELEASE_SHA"' in content
    assert "waiver_manifest_path:" in content
    assert "^infra/release/waivers/" in content
    assert '--waiver-manifest "../$WAIVER_MANIFEST_PATH"' in content
    assert "if: always()" in content
    upload_artifact_refs = re.findall(
        r"uses:\s+actions/upload-artifact@([^\s#]+)", content
    )
    assert upload_artifact_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in upload_artifact_refs)
    assert "continue-on-error" not in content
    assert "npm audit fix --force" not in content


def test_pr18_release_workflow_does_not_claim_registry_attestation():
    content = WORKFLOW.read_text(encoding="utf-8")

    assert "attest-sbom" not in content
    assert "attested: true" not in content
    assert "id-token: write" not in content
