import sys

from scripts.export_openapi import DEFAULT_OUTPUT, build_contract, main, serialize_contract


def test_committed_openapi_contract_matches_application() -> None:
    assert DEFAULT_OUTPUT.is_file(), "Generate backend/openapi/rotas-v1.json."
    assert DEFAULT_OUTPUT.read_bytes() == serialize_contract(build_contract())


def test_openapi_contract_exposes_versioned_api() -> None:
    paths = build_contract()["paths"]
    assert len(paths) >= 295
    unversioned_paths = {path for path in paths if not path.startswith("/api/v1/")}
    assert unversioned_paths == {"/health/deep", "/version"}


def test_check_fails_closed_when_versioned_contract_drifts(tmp_path, monkeypatch) -> None:
    drifted = tmp_path / "rotas-v1.json"
    drifted.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["export_openapi.py", "--check", "--output", str(drifted)])

    assert main() == 1
