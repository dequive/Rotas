"""Fail closed when GitHub workflows use mutable or unapproved Actions."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

USES_LINE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
APPROVED_OWNERS = frozenset({"actions", "dequive"})


@dataclass(frozen=True)
class Finding:
    path: Path
    reference: str
    reason: str


def workflow_files(root: Path) -> list[Path]:
    return sorted((*root.glob("*.yml"), *root.glob("*.yaml")))


def validate_reference(path: Path, reference: str) -> Finding | None:
    if reference.startswith("./"):
        return None
    if "@" not in reference:
        return Finding(path, reference, "remote Action must include an @<sha> reference")

    action, revision = reference.rsplit("@", 1)
    parts = action.split("/")
    if len(parts) < 2 or not parts[0]:
        return Finding(path, reference, "remote Action must use owner/repository syntax")
    if parts[0] not in APPROVED_OWNERS:
        return Finding(path, reference, f"owner {parts[0]!r} is not approved")
    if not FULL_SHA.fullmatch(revision):
        return Finding(path, reference, "Action must be pinned to a lowercase 40-character SHA")
    return None


def evaluate(root: Path) -> tuple[int, list[Finding]]:
    files = workflow_files(root)
    if not files:
        return 0, [Finding(root, "", "no workflow YAML files found")]

    references = 0
    findings: list[Finding] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in USES_LINE.finditer(text):
            references += 1
            reference = match.group(1)
            finding = validate_reference(path, reference)
            if finding is not None:
                findings.append(finding)
    return references, findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow_dir", type=Path)
    args = parser.parse_args()

    references, findings = evaluate(args.workflow_dir.resolve())
    if findings:
        print("GitHub Actions supply-chain policy failed:")
        for finding in findings:
            print(f"- {finding.path}: {finding.reference or '<none>'}: {finding.reason}")
        return 1

    print(f"GitHub Actions supply-chain policy valid: {references} pinned reference(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
