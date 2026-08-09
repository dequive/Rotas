from alembic.config import Config
from alembic.script import ScriptDirectory

from app.database import Base, import_all_models


def test_migration_graph_has_single_rec14_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["rec14"]
    for revision in (
        "1e006dfe187d",
        "rec03",
        "rec04",
        "d8a499250d84",
        "rec06",
        "rec07",
        "cat02",
        "opt01",
        "rec08",
        "rec09",
        "rec10",
        "rec11",
        "rec12",
        "rec13",
        "rec14",
    ):
        assert script.get_revision(revision) is not None


def test_supplemental_workshop_models_are_registered() -> None:
    import_all_models()

    assert {
        "service_catalog_items",
        "workshop_quotes",
        "vehicle_receptions",
        "service_warranties",
        "work_bays",
    } <= set(Base.metadata.tables)

    reception_fk = next(iter(Base.metadata.tables["billing_documents"].c.reception_id.foreign_keys))
    assert reception_fk.column.table.name == "vehicle_receptions"
