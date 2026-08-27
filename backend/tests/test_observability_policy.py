from pathlib import Path

from scripts.validate_observability import validate_observability_policy

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_observability_baseline_is_complete_and_fail_closed():
    assert validate_observability_policy(REPO_ROOT) == {
        "slos": 4,
        "alerts": 5,
        "dashboard_panels": 10,
        "pinned_images": 3,
        "multiprocess_metrics": 1,
        "worker_runtime_metrics": 2,
    }
