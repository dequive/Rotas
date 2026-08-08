import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "backend" / "scripts" / "pr05_snapshot_upgrade_gate.ps1"
EVIDENCE_TEMPLATE = (
    REPO_ROOT / "infra" / "release" / "PR05_ANONYMIZATION_EVIDENCE.template.json"
)
INTEGRITY_SQL = REPO_ROOT / "infra" / "release" / "PR05_INTEGRITY.sql"


def test_pr05_gate_is_fail_closed_and_pins_alembic_to_target() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "[ValidatePattern(\"^rotas_pr05_" in source
    assert "[ValidateSet(\"synthetic\", \"staging_anonymized\", \"production_anonymized\")]" in source
    assert "Anonymization evidence must assert contains_live_pii=false." in source
    assert "Anonymization evidence must assert anonymization_approved=true." in source
    assert "$env:DATABASE_URL = $targetDatabaseUrl" in source
    assert "$env:ALEMBIC_DATABASE_URL = $targetDatabaseUrl" in source
    assert "$targetIntegrity.hash -ne $sourceIntegrity.hash" in source
    assert "$env:ALEMBIC_DATABASE_URL = $previousAlembicDatabaseUrl" in source


def test_pr05_templates_cannot_be_mistaken_for_approved_evidence() -> None:
    evidence = json.loads(EVIDENCE_TEMPLATE.read_text(encoding="utf-8"))
    integrity_sql = INTEGRITY_SQL.read_text(encoding="utf-8")

    assert evidence["schema_version"] == 1
    assert evidence["contains_live_pii"] is True
    assert evidence["anonymization_approved"] is False
    assert not evidence["reviewed_by"]
    assert "accounting_journal_items" in integrity_sql
    assert "journal_debit" in integrity_sql
    assert "journal_credit" in integrity_sql
