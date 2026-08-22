import tomllib
from pathlib import Path

from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_FAMILY = {
    "fastapi": "0.136.3",
    "pydantic": "2.13.4",
    "pydantic-settings": "2.14.1",
    "starlette": "1.2.0",
    "prometheus-client": "0.25.0",
    "prometheus-fastapi-instrumentator": "8.0.0",
}


def test_direct_framework_runtime_dependencies_are_exact_and_coherent():
    pyproject = tomllib.loads(
        (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements = [
        Requirement(raw) for raw in pyproject["project"]["dependencies"]
    ]
    dependencies = {
        requirement.name.lower(): requirement for requirement in requirements
    }

    for package, expected_version in FRAMEWORK_FAMILY.items():
        assert package in dependencies
        assert str(dependencies[package].specifier) == f"=={expected_version}"
