from pathlib import Path

from scripts.validate_runtime_lock import validate_runtime_lock

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_lock_is_complete_hashed_and_used_by_docker():
    result = validate_runtime_lock(REPO_ROOT)
    assert result["direct_dependencies"] >= 20
    assert result["locked_packages"] >= result["direct_dependencies"]
    assert result["sha256_hashes"] >= result["locked_packages"]
