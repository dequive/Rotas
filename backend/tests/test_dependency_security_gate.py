from datetime import UTC, datetime

from scripts.dependency_security_gate import evaluate_dependency_security

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"
NOW = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)


def _audit(*, high: int = 0, critical: int = 0) -> dict:
    vulnerabilities = {}
    for index in range(high):
        package = "next" if index == 0 else f"high-package-{index + 1}"
        vulnerabilities[package] = {
            "severity": "high",
            "range": ">=16.0.0 <16.2.13",
            "via": [
                {
                    "source": 123,
                    "url": "https://github.com/advisories/GHSA-example",
                }
            ],
        }
    for index in range(critical):
        vulnerabilities[f"critical-package-{index + 1}"] = {
            "severity": "critical",
            "range": "<2.0.0",
            "via": [{"source": 456 + index}],
        }
    return {
        "auditReportVersion": 2,
        "metadata": {
            "vulnerabilities": {
                "info": 0,
                "low": 0,
                "moderate": 0,
                "high": high,
                "critical": critical,
                "total": high + critical,
            }
        },
        "vulnerabilities": vulnerabilities,
    }


def test_dependency_security_gate_passes_only_clean_node20_release_fragment():
    result = evaluate_dependency_security(
        production_audit=_audit(),
        complete_audit=_audit(),
        production_audit_exit_code=0,
        complete_audit_exit_code=0,
        tree_exit_code=0,
        tree={},
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.19.0",
        npm_version="10.9.0",
        profile="release_candidate",
        release_sha=RELEASE_SHA,
        sbom_sha256="a" * 64,
    )

    assert result["passed"] is True
    assert result["blockers"] == []
    assert result["policy_id"] == "PR18-DEPENDENCY-SECURITY-V2"
    assert result["sbom"]["attested"] is False


def test_dependency_security_gate_reports_audit_tree_runtime_and_sha_blockers():
    result = evaluate_dependency_security(
        production_audit=_audit(high=3),
        complete_audit=_audit(high=17),
        production_audit_exit_code=1,
        complete_audit_exit_code=1,
        tree_exit_code=1,
        tree={"problems": ["invalid: esbuild"]},
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v24.16.0",
        npm_version="11.13.0",
        profile="release_candidate",
        release_sha="working-tree",
        sbom_sha256="b" * 64,
    )

    assert result["passed"] is False
    assert result["blockers"] == [
        "production_no_unwaived_high_critical",
        "complete_no_unwaived_high_critical",
        "dependency_tree_valid",
        "node_20",
        "release_sha_bound",
    ]
    assert result["vulnerable_production_packages"] == [
        "high-package-2",
        "high-package-3",
        "next",
    ]


def test_dependency_security_gate_accepts_pinned_sharp_platform_artifacts():
    wasm_problem = (
        "extraneous: @img/sharp-wasm32@0.35.4 "
        "/workspace/node_modules/@img/sharp-wasm32"
    )
    runtime_problem = (
        "extraneous: @emnapi/runtime@1.11.3 "
        "/workspace/node_modules/@emnapi/runtime"
    )
    result = evaluate_dependency_security(
        production_audit=_audit(),
        complete_audit=_audit(),
        production_audit_exit_code=0,
        complete_audit_exit_code=0,
        tree_exit_code=0,
        tree={
            "problems": [runtime_problem, wasm_problem],
            "dependencies": {
                "@img/sharp-wasm32": {
                    "version": "0.35.4",
                    "resolved": (
                        "https://registry.npmjs.org/@img/sharp-wasm32/"
                        "-/sharp-wasm32-0.35.4.tgz"
                    ),
                    "extraneous": True,
                    "problems": [wasm_problem],
                    "dependencies": {
                        "@emnapi/runtime": {"version": "1.11.3"},
                    },
                },
                "@emnapi/runtime": {
                    "version": "1.11.3",
                    "resolved": (
                        "https://registry.npmjs.org/@emnapi/runtime/"
                        "-/runtime-1.11.3.tgz"
                    ),
                    "extraneous": True,
                    "problems": [runtime_problem],
                },
            },
        },
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.20.2",
        npm_version="10.8.2",
        profile="local",
        release_sha=None,
        sbom_sha256="f" * 64,
    )

    assert result["passed"] is True
    assert result["dependency_tree"]["accepted_platform_artifacts"] == [
        "@emnapi/runtime@1.11.3",
        "@img/sharp-wasm32@0.35.4",
    ]


def test_dependency_security_gate_rejects_unpinned_sharp_platform_artifact():
    problem = (
        "extraneous: @img/sharp-wasm32@0.35.5 "
        "/workspace/node_modules/@img/sharp-wasm32"
    )
    result = evaluate_dependency_security(
        production_audit=_audit(),
        complete_audit=_audit(),
        production_audit_exit_code=0,
        complete_audit_exit_code=0,
        tree_exit_code=0,
        tree={
            "problems": [problem],
            "dependencies": {
                "@img/sharp-wasm32": {
                    "version": "0.35.5",
                    "extraneous": True,
                    "problems": [problem],
                },
            },
        },
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.20.2",
        npm_version="10.8.2",
        profile="local",
        release_sha=None,
        sbom_sha256="f" * 64,
    )

    assert result["passed"] is False
    assert result["dependency_tree"]["unexpected_problems"] == [problem]


def _waiver(*, release_sha: str = RELEASE_SHA, approved: bool = True) -> dict:
    return {
        "schema_version": 1,
        "release_sha": release_sha,
        "waivers": [
            {
                "id": "PR18-NEXT-001",
                "package": "next",
                "severity": "high",
                "affected_range": ">=16.0.0 <16.2.13",
                "advisories": ["https://github.com/advisories/GHSA-example"],
                "justification": (
                    "Upstream stable release is pending while runtime exposure "
                    "is restricted."
                ),
                "compensating_controls": [
                    "WAF rule blocks the affected request pattern.",
                    "Runtime alert detects attempted exploitation.",
                ],
                "tracking_url": "https://tracker.example.test/SEC-123",
                "owner": {"identifier": "security-owner", "role": "SEC"},
                "created_at": "2026-07-31T10:00:00Z",
                "expires_at": "2026-08-15T10:00:00Z",
                "approvals": [
                    {
                        "role": "SEC",
                        "approver": "security-approver",
                        "approved": approved,
                        "release_sha": release_sha,
                        "signed_at": "2026-07-31T10:30:00Z",
                    },
                    {
                        "role": "TL",
                        "approver": "technical-lead",
                        "approved": approved,
                        "release_sha": release_sha,
                        "signed_at": "2026-07-31T10:31:00Z",
                    },
                ],
            }
        ],
    }


def _evaluate_with_waiver(waiver: dict, *, critical: int = 0) -> dict:
    return evaluate_dependency_security(
        production_audit=_audit(high=1, critical=critical),
        complete_audit=_audit(high=1, critical=critical),
        production_audit_exit_code=1,
        complete_audit_exit_code=1,
        tree_exit_code=0,
        tree={},
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.20.2",
        npm_version="10.8.2",
        profile="release_candidate",
        release_sha=RELEASE_SHA,
        sbom_sha256="c" * 64,
        waiver_manifest=waiver,
        evaluated_at=NOW,
    )


def test_dependency_security_gate_accepts_fully_approved_sha_bound_high_waiver():
    result = _evaluate_with_waiver(_waiver())

    assert result["passed"] is True
    assert result["security_waivers"]["valid_waiver_ids"] == ["PR18-NEXT-001"]
    assert result["security_waivers"]["production_unwaived"] == []


def test_dependency_security_gate_rejects_unapproved_or_wrong_sha_waiver():
    waiver = _waiver(approved=False)
    waiver["release_sha"] = "f" * 40

    result = _evaluate_with_waiver(waiver)

    assert result["passed"] is False
    assert result["checks"]["waiver_manifest_valid"] is False
    assert result["security_waivers"]["production_unwaived"]
    assert any(
        "bound to the release SHA" in error
        for error in result["security_waivers"]["errors"]
    )
    assert any("is not approved" in error for error in result["security_waivers"]["errors"])


def test_dependency_security_gate_rejects_expired_waiver_and_critical_findings():
    waiver = _waiver()
    waiver["waivers"][0]["expires_at"] = "2026-07-31T11:00:00Z"

    result = _evaluate_with_waiver(waiver, critical=1)

    assert result["passed"] is False
    assert any("is expired" in error for error in result["security_waivers"]["errors"])
    assert any(
        finding["severity"] == "critical"
        for finding in result["security_waivers"]["production_unwaived"]
    )


def test_dependency_security_gate_rejects_audit_count_without_matching_findings():
    audit = _audit()
    audit["metadata"]["vulnerabilities"]["high"] = 1
    audit["metadata"]["vulnerabilities"]["total"] = 1

    result = evaluate_dependency_security(
        production_audit=audit,
        complete_audit=audit,
        production_audit_exit_code=1,
        complete_audit_exit_code=1,
        tree_exit_code=0,
        tree={},
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.20.2",
        npm_version="10.8.2",
        profile="release_candidate",
        release_sha=RELEASE_SHA,
        sbom_sha256="d" * 64,
    )

    assert result["passed"] is False
    assert result["checks"]["audit_findings_consistent"] is False


def test_dependency_security_gate_rejects_exit_one_with_empty_audit_payload():
    result = evaluate_dependency_security(
        production_audit=_audit(),
        complete_audit=_audit(),
        production_audit_exit_code=1,
        complete_audit_exit_code=0,
        tree_exit_code=0,
        tree={},
        sbom={"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{}]},
        node_version="v20.20.2",
        npm_version="10.8.2",
        profile="local",
        release_sha=None,
        sbom_sha256="e" * 64,
    )

    assert result["passed"] is False
    assert result["checks"]["audit_commands_valid"] is False
    assert "audit_commands_valid" in result["blockers"]
