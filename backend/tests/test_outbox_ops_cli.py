from argparse import Namespace
from uuid import uuid4

import pytest

from scripts.outbox_ops import _parser, _request_spec


def test_cli_builds_filtered_tenant_list_request():
    args = _parser().parse_args(
        [
            "--tenant-id",
            str(uuid4()),
            "list",
            "--status",
            "dead_letter",
            "--event-type",
            "trip.incident",
            "--limit",
            "25",
        ]
    )

    method, path, options = _request_spec(args)

    assert method == "GET"
    assert path == "/api/v1/outbox-events"
    assert options == {
        "params": {
            "limit": 25,
            "status": "dead_letter",
            "event_type": "trip.incident",
        }
    }


def test_cli_builds_replay_with_reason():
    event_id = uuid4()
    args = Namespace(
        command="replay",
        event_id=event_id,
        reason="Contrato upstream corrigido.",
    )

    method, path, options = _request_spec(args)

    assert method == "POST"
    assert path == f"/api/v1/outbox-events/{event_id}/replay"
    assert options == {"json": {"reason": "Contrato upstream corrigido."}}


def test_cli_rejects_unexplained_replay():
    with pytest.raises(ValueError, match="at least 10"):
        _request_spec(
            Namespace(
                command="replay",
                event_id=uuid4(),
                reason="retry",
            )
        )
