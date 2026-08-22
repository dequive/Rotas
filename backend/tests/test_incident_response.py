import json
from pathlib import Path

import pytest

from scripts.incident_game_day import (
    IncidentGameDayError,
    build_local_tabletop_report,
)
from scripts.validate_incident_response import validate_incident_response_policy

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_incident_response_policy_is_complete_and_fail_closed():
    assert validate_incident_response_policy(REPO_ROOT) == {
        "severities": 4,
        "roles": 6,
        "lifecycle_states": 7,
        "scenarios": 5,
    }


def test_local_tabletop_cannot_promote_production_gate():
    report = build_local_tabletop_report(REPO_ROOT, "working-tree")

    assert report["status"] == "tabletop_passed"
    assert report["evidence_scope"] == "local_control_plane_only"
    assert report["gate_effect"] == "none"
    assert len(report["scenarios"]) == 5
    assert "real_paging_delivery" in report["unproven"]


def test_local_tabletop_requires_a_release_reference():
    with pytest.raises(IncidentGameDayError):
        build_local_tabletop_report(REPO_ROOT, "  ")


def test_policy_contains_no_versioned_people_or_contacts():
    policy = json.loads(
        (
            REPO_ROOT / "infra" / "operations" / "INCIDENT_RESPONSE_POLICY.json"
        ).read_text(encoding="utf-8")
    )

    assert policy["roster"]["people_or_contacts_in_repository"] is False
    assert policy["communication"]["paging_endpoint_source"] == "external_secret"
