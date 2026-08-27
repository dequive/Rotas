import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGER = REPO_ROOT / "apps" / "manager"
NEXT_IMAGE_IMPORT = re.compile(
    r"""(?:from\s+|require\(\s*)["']next/image["']"""
)


def test_manager_disables_unused_next_image_optimizer():
    config = (MANAGER / "next.config.mjs").read_text(encoding="utf-8")

    assert "images:" in config
    assert "unoptimized: true" in config
    assert "remotePatterns" not in config
    assert "dangerouslyAllowLocalIP" not in config
    assert "dangerouslyAllowSVG" not in config


def test_manager_has_no_next_image_imports():
    source_roots = [MANAGER / "app", MANAGER / "components"]
    source_files = []
    for source_root in source_roots:
        for pattern in ("*.ts", "*.tsx", "*.js", "*.mjs"):
            source_files.extend(source_root.rglob(pattern))
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in source_files
        if NEXT_IMAGE_IMPORT.search(
            path.read_text(encoding="utf-8", errors="ignore")
        )
    ]

    assert offenders == []


def test_manager_runtime_image_uses_standalone_output_only():
    dockerfile = (MANAGER / "Dockerfile").read_text(encoding="utf-8")
    package = (MANAGER / "package.json").read_text(encoding="utf-8")
    ci_workflow = (
        REPO_ROOT / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    prune_script = (
        MANAGER / "scripts" / "prune-unused-image-optimizer.mjs"
    ).read_text(encoding="utf-8")

    assert "/workspace/apps/manager/.next/standalone" in dockerfile
    assert "npm ci --include=optional" in dockerfile
    assert "@next/swc-linux-x64-gnu/next-swc.linux-x64-gnu.node" in dockerfile
    assert "RUN --network=none npm --workspace apps/manager run build" in dockerfile
    assert "COPY --from=dependencies" not in dockerfile
    assert "COPY --from=builder --chown=node:node /workspace/node_modules" not in dockerfile
    assert "next build && node scripts/prune-unused-image-optimizer.mjs" in package
    assert "PR18-MANAGER-RUNTIME-SURFACE-V1" in prune_script
    assert 'path.resolve(standaloneRoot, "node_modules", "sharp")' in prune_script
    assert "assertInsideStandalone(target)" in prune_script
    assert "permissions:\n  contents: read" in ci_workflow


def test_manager_declares_linux_swc_as_locked_optional_dependency():
    package = json.loads((MANAGER / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    next_version = package["dependencies"]["next"]
    swc_version = package["optionalDependencies"]["@next/swc-linux-x64-gnu"]

    assert swc_version == next_version
    assert lock["packages"]["apps/manager"]["dependencies"]["next"] == next_version
    assert (
        lock["packages"]["apps/manager"]["optionalDependencies"]
        ["@next/swc-linux-x64-gnu"]
        == next_version
    )
    assert lock["packages"]["node_modules/next"]["version"] == next_version
    assert (
        lock["packages"]["node_modules/@next/swc-linux-x64-gnu"]["version"]
        == next_version
    )
