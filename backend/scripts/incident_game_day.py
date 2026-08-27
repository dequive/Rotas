"""Generate a bounded local tabletop report for the PR-25 control plane."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.validate_incident_response import (
    load_incident_policy,
    validate_incident_response_policy,
)

CONFIRMATION = "PR25-LOCAL-TABLETOP"


class IncidentGameDayError(ValueError):
    pass


def build_local_tabletop_report(repo_root: Path, release_ref: str) -> dict[str, Any]:
    validation = validate_incident_response_policy(repo_root)
    policy = load_incident_policy(repo_root)
    if not release_ref.strip():
        raise IncidentGameDayError("Release reference must not be empty.")

    scenarios = []
    for scenario in policy["scenarios"]:
        scenarios.append(
            {
                "id": scenario["id"],
                "severity": scenario["severity"],
                "signal": scenario["signal"],
                "runbook": scenario["runbook"],
                "controls_reviewed": scenario["expected_controls"],
                "result": "tabletop_control_path_present",
            }
        )

    return {
        "schema_version": 1,
        "policy_id": policy["policy_id"],
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "release_ref": release_ref,
        "status": "tabletop_passed",
        "evidence_scope": "local_control_plane_only",
        "gate_effect": "none",
        "validation": validation,
        "scenarios": scenarios,
        "unproven": [
            "real_paging_delivery",
            "human_acknowledgement_and_escalation",
            "production_like_failure_injection",
            "measured_containment_and_recovery",
            "measured_rpo_and_rto",
            "independent_operator_and_sign_off",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--release-ref", required=True)
    parser.add_argument("--confirm-local-tabletop", required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    args = parser.parse_args()

    if args.confirm_local_tabletop != CONFIRMATION:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": f"Confirmation must equal {CONFIRMATION}.",
                },
                indent=2,
            )
        )
        return 1

    try:
        report = build_local_tabletop_report(
            args.repo_root.resolve(), args.release_ref
        )
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, json.JSONDecodeError, IncidentGameDayError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
