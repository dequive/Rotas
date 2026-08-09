"""Unit tests for the GitHub Actions supply-chain validator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_action_pins import evaluate, validate_reference

PIN = "11d5960a326750d5838078e36cf38b85af677262"


class ActionPinPolicyTests(unittest.TestCase):
    def test_accepts_approved_owner_with_full_sha(self) -> None:
        self.assertIsNone(validate_reference(Path("ci.yml"), f"actions/checkout@{PIN}"))

    def test_accepts_repository_local_action(self) -> None:
        self.assertIsNone(validate_reference(Path("ci.yml"), "./.github/actions/setup"))

    def test_rejects_mutable_tag(self) -> None:
        finding = validate_reference(Path("ci.yml"), "actions/checkout@v4")
        self.assertIsNotNone(finding)
        self.assertIn("40-character SHA", finding.reason)

    def test_rejects_unapproved_owner(self) -> None:
        finding = validate_reference(Path("ci.yml"), f"third-party/tool@{PIN}")
        self.assertIsNotNone(finding)
        self.assertIn("not approved", finding.reason)

    def test_evaluates_every_workflow_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ci.yml").write_text(
                f"jobs:\n  test:\n    steps:\n      - uses: actions/checkout@{PIN} # v4\n",
                encoding="utf-8",
            )
            references, findings = evaluate(root)
        self.assertEqual(references, 1)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
