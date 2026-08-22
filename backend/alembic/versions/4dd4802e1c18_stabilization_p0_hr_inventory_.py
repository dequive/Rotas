"""stabilization_p0_hr_inventory_accounting_outbox (P0-F1 + P0-F5 + P0-F8)

Creates HR, Inventory, and outbox_events tables plus a description column on
accounting_journal_items. Every table with ``tenant_id`` carries RLS (ENABLE,
FORCE, policy) and ``GRANT TO rotas_app`` per the v2.0 migration rule.

Revision ID: 4dd4802e1c18
Revises: 92c11f6fdf9d
Create Date: 2026-07-20 22:18:04.826285+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = '4dd4802e1c18'
down_revision: str | None = '92c11f6fdf9d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_TABLE_COLUMNS = {
    "employees": {
        "id", "tenant_id", "driver_id", "user_id", "first_name", "last_name",
        "role", "department", "employee_number", "inss_beneficiary_number",
        "professional_category", "irps_tax_percentage", "base_salary", "nif_nuit",
        "bank_account_nib", "date_of_birth", "hire_date", "termination_date",
        "status", "created_at", "updated_at",
    },
    "employee_documents": {
        "id", "tenant_id", "employee_id", "document_type", "document_number",
        "issued_at", "expiry_date", "file_id", "status", "notes", "created_at",
    },
    "absences": {
        "id", "tenant_id", "employee_id", "absence_type", "start_date", "end_date",
        "is_paid", "approved_by", "notes", "created_at",
    },
    "payroll_slips": {
        "id", "tenant_id", "employee_id", "period_month", "period_year",
        "gross_salary", "total_inss", "total_irps", "total_syndicate",
        "total_deductions", "net_salary", "status", "payment_date", "notes",
        "created_at", "updated_at",
    },
    "payroll_codes": {
        "id", "tenant_id", "code", "name", "code_type", "is_taxable_inss",
        "is_taxable_irps", "is_taxable_syndicate", "created_at",
    },
    "payroll_slip_lines": {
        "id", "tenant_id", "payroll_slip_id", "code", "description", "quantity",
        "unit_price", "amount", "irps_tax_percentage", "is_taxable_inss",
        "is_taxable_syndicate", "created_at",
    },
    "salary_advances": {
        "id", "tenant_id", "employee_id", "amount", "date_requested", "status",
        "reason", "created_at", "updated_at",
    },
    "warehouses": {"id", "tenant_id", "name", "location", "is_active"},
    "item_categories": {"id", "tenant_id", "name"},
    "items": {
        "id", "tenant_id", "category_id", "sku", "name", "description",
        "unit_of_measure", "current_stock", "average_unit_cost",
    },
    "stock_movements": {
        "id", "tenant_id", "item_id", "warehouse_id", "movement_type", "quantity",
        "unit_cost", "total_value", "reference_doc", "notes", "created_by",
    },
}


def _rls(tablename: str) -> None:
    """Apply v2.0 RLS + GRANT boilerplate for a tenant-scoped table."""
    op.execute(f"ALTER TABLE {tablename} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tablename} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY rls_{tablename} ON {tablename} "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tablename} TO rotas_app")


def _create_outbox_events() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(128), nullable=True),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("governance_case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_tenant_id", "outbox_events", ["tenant_id"])
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    op.create_index("ix_outbox_events_next_attempt_at", "outbox_events", ["next_attempt_at"])
    _rls("outbox_events")


def _drop_rls(tablename: str) -> None:
    """Reverse the _rls() block."""
    op.execute(f"DROP POLICY IF EXISTS rls_{tablename} ON {tablename}")
    op.execute(f"ALTER TABLE {tablename} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tablename} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    legacy_existing = set(_LEGACY_TABLE_COLUMNS) & existing_tables
    if legacy_existing:
        # Some pre-stabilization databases materialized the HR/inventory ORM
        # schema while Alembic remained stamped at 95929ae669b9/92c11f6fdf9d.
        # Reconcile only a complete, structurally identical snapshot. A partial
        # or divergent snapshot must stop for forensic repair rather than being
        # silently stamped.
        if legacy_existing != set(_LEGACY_TABLE_COLUMNS):
            missing = sorted(set(_LEGACY_TABLE_COLUMNS) - legacy_existing)
            raise RuntimeError(
                "Partial legacy HR/inventory snapshot; missing tables: "
                + ", ".join(missing)
            )
        for table_name, expected_columns in _LEGACY_TABLE_COLUMNS.items():
            actual_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            if actual_columns != expected_columns:
                missing = sorted(expected_columns - actual_columns)
                extra = sorted(actual_columns - expected_columns)
                raise RuntimeError(
                    f"Legacy table {table_name} diverges; "
                    f"missing={missing}, extra={extra}"
                )
        journal_columns = {
            column["name"]
            for column in inspector.get_columns("accounting_journal_items")
        }
        if "description" not in journal_columns:
            raise RuntimeError(
                "Legacy HR/inventory snapshot lacks "
                "accounting_journal_items.description"
            )
        for table_name in _LEGACY_TABLE_COLUMNS:
            _rls(table_name)
        if "outbox_events" not in existing_tables:
            _create_outbox_events()
        return

    # ----------------------------------------------------------------
    # 1. accounting_journal_items.description (model drift from new ORM)
    # ----------------------------------------------------------------
    op.add_column(
        "accounting_journal_items",
        sa.Column("description", sa.Text(), nullable=True),
    )

    # ----------------------------------------------------------------
    # 2. HR tables
    # ----------------------------------------------------------------
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(80), nullable=False),
        sa.Column("department", sa.String(80), nullable=False),
        sa.Column("employee_number", sa.String(40), nullable=True),
        sa.Column("inss_beneficiary_number", sa.String(80), nullable=True),
        sa.Column("professional_category", sa.String(100), nullable=True),
        sa.Column("irps_tax_percentage", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("base_salary", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("nif_nuit", sa.String(40), nullable=True),
        sa.Column("bank_account_nib", sa.String(80), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "nif_nuit", name="uq_employees_tenant_nif"),
    )
    op.create_index("ix_employees_tenant_id", "employees", ["tenant_id"])
    op.create_index("ix_employees_driver_id", "employees", ["driver_id"])
    op.create_index("ix_employees_user_id", "employees", ["user_id"])
    op.create_index("ix_employees_status", "employees", ["status"])
    _rls("employees")

    op.create_table(
        "employee_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("document_number", sa.String(80), nullable=True),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'valid'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_documents_tenant_id", "employee_documents", ["tenant_id"])
    op.create_index("ix_employee_documents_employee_id", "employee_documents", ["employee_id"])
    op.create_index("ix_employee_documents_expiry_date", "employee_documents", ["expiry_date"])
    op.create_index("ix_employee_documents_status", "employee_documents", ["status"])
    _rls("employee_documents")

    op.create_table(
        "absences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("absence_type", sa.String(40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_absences_tenant_id", "absences", ["tenant_id"])
    op.create_index("ix_absences_employee_id", "absences", ["employee_id"])
    _rls("absences")

    op.create_table(
        "payroll_slips",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("gross_salary", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_inss", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_irps", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_syndicate", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("net_salary", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "employee_id", "period_month", "period_year",
            name="uq_payroll_slips_tenant_emp_period",
        ),
    )
    op.create_index("ix_payroll_slips_tenant_id", "payroll_slips", ["tenant_id"])
    op.create_index("ix_payroll_slips_employee_id", "payroll_slips", ["employee_id"])
    op.create_index("ix_payroll_slips_status", "payroll_slips", ["status"])
    _rls("payroll_slips")

    op.create_table(
        "payroll_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code_type", sa.String(20), nullable=False),
        sa.Column("is_taxable_inss", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_taxable_irps", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_taxable_syndicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payroll_codes_tenant_id", "payroll_codes", ["tenant_id"])
    _rls("payroll_codes")

    op.create_table(
        "payroll_slip_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payroll_slip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.String(100), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("irps_tax_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_taxable_inss", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_taxable_syndicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["payroll_slip_id"], ["payroll_slips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payroll_slip_lines_tenant_id", "payroll_slip_lines", ["tenant_id"])
    op.create_index("ix_payroll_slip_lines_payroll_slip_id", "payroll_slip_lines", ["payroll_slip_id"])
    _rls("payroll_slip_lines")

    op.create_table(
        "salary_advances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("date_requested", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_salary_advances_tenant_id", "salary_advances", ["tenant_id"])
    op.create_index("ix_salary_advances_employee_id", "salary_advances", ["employee_id"])
    op.create_index("ix_salary_advances_status", "salary_advances", ["status"])
    _rls("salary_advances")

    # ----------------------------------------------------------------
    # 3. Inventory tables
    # ----------------------------------------------------------------
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_warehouses_tenant_id", "warehouses", ["tenant_id"])
    _rls("warehouses")

    op.create_table(
        "item_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_categories_tenant_id", "item_categories", ["tenant_id"])
    _rls("item_categories")

    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sku", sa.String(50), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_of_measure", sa.String(20), nullable=False, server_default=sa.text("'UN'")),
        sa.Column("current_stock", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("average_unit_cost", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0.00")),
        sa.ForeignKeyConstraint(["category_id"], ["item_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_tenant_id", "items", ["tenant_id"])
    op.create_index("ix_items_category_id", "items", ["category_id"])
    _rls("items")

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_value", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference_doc", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_movements_tenant_id", "stock_movements", ["tenant_id"])
    op.create_index("ix_stock_movements_item_id", "stock_movements", ["item_id"])
    op.create_index("ix_stock_movements_warehouse_id", "stock_movements", ["warehouse_id"])
    _rls("stock_movements")

    # ----------------------------------------------------------------
    # 4. Outbox events (Governance Engine P0-F8)
    # ----------------------------------------------------------------
    _create_outbox_events()


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("stock_movements")
    op.drop_table("items")
    op.drop_table("item_categories")
    op.drop_table("warehouses")
    op.drop_table("salary_advances")
    op.drop_table("payroll_slip_lines")
    op.drop_table("payroll_codes")
    op.drop_table("payroll_slips")
    op.drop_table("absences")
    op.drop_table("employee_documents")
    op.drop_table("employees")
    op.drop_column("accounting_journal_items", "description")
