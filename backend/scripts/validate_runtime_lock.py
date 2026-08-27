"""Fail-closed validation for the production Python dependency lock."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version

_LOCKED_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[A-Za-z0-9_.+!-]+)\s*\\?$"
)
_HASH = "--hash=sha256:"
_FORBIDDEN = ("-e ", "--editable", " @ ", "git+", "pytest==", "ruff==", "pyright==")


class RuntimeLockError(ValueError):
    pass


def validate_runtime_lock(repo_root: Path) -> dict[str, int]:
    pyproject_path = repo_root / "backend" / "pyproject.toml"
    lock_path = repo_root / "backend" / "requirements.lock"
    dockerfile_path = repo_root / "backend" / "Dockerfile"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    lock = lock_path.read_text(encoding="utf-8")
    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    failures: list[str] = []

    locked: dict[str, Version] = {}
    for line in lock.splitlines():
        match = _LOCKED_REQUIREMENT.match(line.strip())
        if match:
            locked[match.group("name").lower()] = Version(match.group("version"))

    direct = [Requirement(raw) for raw in pyproject["project"]["dependencies"]]
    for requirement in direct:
        name = requirement.name.lower()
        version = locked.get(name)
        if version is None:
            failures.append(f"Direct runtime dependency is absent from lock: {name}")
        elif requirement.specifier and version not in requirement.specifier:
            failures.append(
                f"Locked {name} {version} violates {requirement.specifier}."
            )

    hash_count = lock.count(_HASH)
    if len(locked) < len(direct):
        failures.append("Runtime lock cannot contain fewer packages than direct dependencies.")
    if hash_count < len(locked):
        failures.append("Every locked package must have at least one SHA-256 hash.")
    for forbidden in _FORBIDDEN:
        if forbidden in lock:
            failures.append(f"Runtime lock contains forbidden development/source entry: {forbidden}")
    for required_control in (
        "COPY backend/pyproject.toml backend/README.md backend/requirements.lock",
        "pip install --require-hashes --requirement requirements.lock",
        "COPY backend/app ./app",
        "pip install --no-deps --no-build-isolation .",
        "pip check",
    ):
        if required_control not in dockerfile:
            failures.append(f"Docker runtime lock control is missing: {required_control}")

    if failures:
        raise RuntimeLockError("; ".join(failures))
    return {
        "direct_dependencies": len(direct),
        "locked_packages": len(locked),
        "sha256_hashes": hash_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    try:
        result = validate_runtime_lock(args.repo_root.resolve())
    except (OSError, RuntimeLockError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
