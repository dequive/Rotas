"""Verify pulled staging images against immutable release metadata."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.validate_staging_manifest import (
    CUSTOM_IMAGE_KEYS,
    RELEASE_SHA,
    StagingManifestError,
    _read_env,
)

EXPECTED_USERS = {
    "ROTAS_BACKEND_IMAGE": "10001:10001",
    "ROTAS_GOVERNANCE_IMAGE": "10001:10001",
    "ROTAS_MANAGER_IMAGE": "node",
    "ROTAS_DRIVER_IMAGE": "1000:1000",
}


def validate_image_inspection(
    image_key: str,
    image_reference: str,
    release_sha: str,
    inspection: dict[str, Any],
) -> dict[str, str]:
    failures: list[str] = []
    repo_digests = inspection.get("RepoDigests") or []
    if image_reference not in repo_digests:
        failures.append("pulled image does not expose the exact requested RepoDigest")

    config = inspection.get("Config") or {}
    actual_user = config.get("User", "")
    expected_user = EXPECTED_USERS[image_key]
    if actual_user != expected_user:
        failures.append(f"runtime user is {actual_user!r}, expected {expected_user!r}")

    labels = config.get("Labels") or {}
    actual_revision = labels.get("org.opencontainers.image.revision", "")
    if actual_revision != release_sha:
        failures.append(
            f"OCI revision is {actual_revision!r}, expected release SHA {release_sha!r}"
        )
    version = labels.get("org.opencontainers.image.version", "")
    if not version or version.lower() in {"dev", "unknown", "latest"}:
        failures.append("OCI version must identify a non-development release")

    if failures:
        raise StagingManifestError(f"{image_key}: " + "; ".join(failures))
    return {
        "reference": image_reference,
        "user": actual_user,
        "revision": actual_revision,
        "version": version,
    }


def inspect_staging_images(env_path: Path) -> dict[str, dict[str, str]]:
    values = _read_env(env_path)
    release_sha = values.get("ROTAS_RELEASE_SHA", "")
    if not RELEASE_SHA.fullmatch(release_sha):
        raise StagingManifestError(
            "ROTAS_RELEASE_SHA must be the full 40-character lowercase Git SHA."
        )

    results: dict[str, dict[str, str]] = {}
    for image_key in sorted(CUSTOM_IMAGE_KEYS):
        image_reference = values.get(image_key, "")
        completed = subprocess.run(
            ["docker", "image", "inspect", image_reference],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            error = completed.stderr.strip() or "docker image inspect failed"
            raise StagingManifestError(f"{image_key}: {error}")
        try:
            payload = json.loads(completed.stdout)
            inspection = payload[0]
        except (IndexError, json.JSONDecodeError, TypeError) as exc:
            raise StagingManifestError(
                f"{image_key}: invalid docker image inspect output"
            ) from exc
        results[image_key] = validate_image_inspection(
            image_key,
            image_reference,
            release_sha,
            inspection,
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        images = inspect_staging_images(args.env_file.resolve())
    except (OSError, StagingManifestError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "images": images}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
