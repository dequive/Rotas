import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DRIVER_PACKAGE = REPO_ROOT / "apps" / "driver" / "package.json"


def test_ci_uses_the_canonical_node_patch_everywhere():
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert content.count('node-version: "20.20.2"') == 2
    assert 'node-version: "20"' not in content


def test_ci_executes_driver_unit_build_and_playwright_gates():
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    required_commands = (
        "npm --workspace apps/driver run test",
        "npm --workspace apps/driver run build",
        "npm --workspace apps/driver run e2e",
    )
    for command in required_commands:
        assert content.count(command) == 1

    assert "npx playwright install --with-deps chromium" in content


def test_driver_build_uses_a_node20_compatible_vite_config_loader():
    package = json.loads(DRIVER_PACKAGE.read_text(encoding="utf-8"))

    assert package["scripts"]["build"] == "tsc && vite build --config vite.config.ts"
    assert package["scripts"]["preview"] == "vite preview --config vite.config.ts"
    assert "--configLoader native" not in " ".join(package["scripts"].values())
