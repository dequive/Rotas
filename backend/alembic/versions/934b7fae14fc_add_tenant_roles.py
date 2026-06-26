"""add_tenant_roles

Revision ID: 934b7fae14fc
Revises: tp09
Create Date: 2026-06-20 11:25:31.415993+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "934b7fae14fc"
down_revision: str | None = "tp09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── tenant_roles table ────────────────────────────────────────────────────
    op.create_table(
        "tenant_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column(
            "permissions",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_tenant_roles_tenant_slug"),
    )
    op.create_index("ix_tenant_roles_tenant_id", "tenant_roles", ["tenant_id"])

    # v2.0 rule: RLS + GRANT in same migration as CREATE TABLE
    op.execute("ALTER TABLE tenant_roles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE tenant_roles FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY rls_tenant_roles ON tenant_roles "
        "USING (tenant_id::text = current_setting('app.tenant_id', true));"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_roles TO rotas_app;")

    # ── Add nullable FK column to users ──────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "custom_role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_roles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_custom_role_id", "users", ["custom_role_id"])

    # ── Index renames detected by autogenerate ────────────────────────────────
    op.drop_index(op.f("ix_dva_driver"), table_name="driver_vehicle_assignments")
    op.drop_index(op.f("ix_dva_tenant"), table_name="driver_vehicle_assignments")
    op.drop_index(op.f("ix_dva_vehicle"), table_name="driver_vehicle_assignments")
    op.create_index(
        op.f("ix_driver_vehicle_assignments_tenant_id"),
        "driver_vehicle_assignments",
        ["tenant_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_fuel_logs_tenant_created_at"), table_name="fuel_logs")
    op.drop_index(op.f("ix_fuel_logs_tenant_vehicle"), table_name="fuel_logs")
    op.drop_index(op.f("ix_fuel_purchases_supplier_tp"), table_name="fuel_purchases")
    op.create_index(
        op.f("ix_fuel_purchases_supplier_third_party_id"),
        "fuel_purchases",
        ["supplier_third_party_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_maintenance_plans_tenant_status_km"), table_name="maintenance_plans")
    op.drop_index(op.f("ix_maintenance_schedule_tenant_status"), table_name="maintenance_schedule")
    op.drop_index(
        op.f("ix_operational_documents_expiry_date"),
        table_name="operational_documents",
        postgresql_where="(expiry_date IS NOT NULL)",
    )
    op.drop_index(op.f("ix_operational_documents_tenant"), table_name="operational_documents")
    op.drop_index(
        op.f("ix_operational_documents_tenant_subject"), table_name="operational_documents"
    )
    op.drop_index(op.f("ix_operational_documents_verification"), table_name="operational_documents")
    op.create_index(
        op.f("ix_operational_documents_tenant_id"),
        "operational_documents",
        ["tenant_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_spare_parts_supplier_tp"), table_name="spare_parts_inventory")
    op.create_index(
        op.f("ix_spare_parts_inventory_supplier_third_party_id"),
        "spare_parts_inventory",
        ["supplier_third_party_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_se_evaluation_date"), table_name="supplier_evaluations")
    op.drop_index(op.f("ix_se_tenant_party"), table_name="supplier_evaluations")
    op.drop_index(op.f("ix_sle_entry_date"), table_name="supplier_ledger_entries")
    op.drop_index(op.f("ix_sle_tenant_party"), table_name="supplier_ledger_entries")
    op.drop_index(op.f("ix_sync_events_tenant_driver"), table_name="sync_events")
    op.drop_index(op.f("ix_third_parties_tenant_status"), table_name="third_parties")
    op.drop_index(op.f("ix_tpc_tenant_party"), table_name="third_party_contacts")
    op.drop_index(op.f("ix_trip_stops_tenant_trip"), table_name="trip_stops")
    op.drop_index(op.f("ix_trips_tenant_actual_departure"), table_name="trips")
    op.drop_index(op.f("ix_trips_tenant_driver_status"), table_name="trips")
    op.drop_index(op.f("ix_trips_tenant_status"), table_name="trips")
    op.drop_index(op.f("ix_trips_tenant_vehicle_status"), table_name="trips")
    op.drop_index(op.f("ix_work_orders_service_provider_tp"), table_name="work_orders")
    op.create_index(
        op.f("ix_work_orders_service_provider_third_party_id"),
        "work_orders",
        ["service_provider_third_party_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_users_custom_role_id", table_name="users")
    op.drop_column("users", "custom_role_id")
    op.execute("DROP POLICY IF EXISTS rls_tenant_roles ON tenant_roles;")
    op.drop_index("ix_tenant_roles_tenant_id", table_name="tenant_roles")
    op.drop_table("tenant_roles")

    # ── Restore renamed indexes ───────────────────────────────────────────────
    op.drop_index(op.f("ix_work_orders_service_provider_third_party_id"), table_name="work_orders")
    op.create_index(
        op.f("ix_work_orders_service_provider_tp"),
        "work_orders",
        ["service_provider_third_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trips_tenant_vehicle_status"),
        "trips",
        ["tenant_id", "vehicle_id", "status"],
        unique=False,
    )
    op.create_index(op.f("ix_trips_tenant_status"), "trips", ["tenant_id", "status"], unique=False)
    op.create_index(
        op.f("ix_trips_tenant_driver_status"),
        "trips",
        ["tenant_id", "driver_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trips_tenant_actual_departure"),
        "trips",
        ["tenant_id", "actual_departure"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_stops_tenant_trip"),
        "trip_stops",
        ["tenant_id", "trip_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tpc_tenant_party"),
        "third_party_contacts",
        ["tenant_id", "third_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_third_parties_tenant_status"),
        "third_parties",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sync_events_tenant_driver"),
        "sync_events",
        ["tenant_id", "driver_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sle_tenant_party"),
        "supplier_ledger_entries",
        ["tenant_id", "third_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sle_entry_date"),
        "supplier_ledger_entries",
        ["tenant_id", "entry_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_se_tenant_party"),
        "supplier_evaluations",
        ["tenant_id", "third_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_se_evaluation_date"),
        "supplier_evaluations",
        ["tenant_id", "evaluation_date"],
        unique=False,
    )
    op.drop_index(
        op.f("ix_spare_parts_inventory_supplier_third_party_id"),
        table_name="spare_parts_inventory",
    )
    op.create_index(
        op.f("ix_spare_parts_supplier_tp"),
        "spare_parts_inventory",
        ["supplier_third_party_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_operational_documents_tenant_id"), table_name="operational_documents")
    op.create_index(
        op.f("ix_operational_documents_verification"),
        "operational_documents",
        ["tenant_id", "verification_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_documents_tenant_subject"),
        "operational_documents",
        ["tenant_id", "subject_type", "subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_documents_tenant"),
        "operational_documents",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operational_documents_expiry_date"),
        "operational_documents",
        ["expiry_date"],
        unique=False,
        postgresql_where="(expiry_date IS NOT NULL)",
    )
    op.create_index(
        op.f("ix_maintenance_schedule_tenant_status"),
        "maintenance_schedule",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_maintenance_plans_tenant_status_km"),
        "maintenance_plans",
        ["tenant_id", "status", "next_due_km"],
        unique=False,
    )
    op.drop_index(op.f("ix_fuel_purchases_supplier_third_party_id"), table_name="fuel_purchases")
    op.create_index(
        op.f("ix_fuel_purchases_supplier_tp"),
        "fuel_purchases",
        ["supplier_third_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fuel_logs_tenant_vehicle"),
        "fuel_logs",
        ["tenant_id", "vehicle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fuel_logs_tenant_created_at"),
        "fuel_logs",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.drop_index(
        op.f("ix_driver_vehicle_assignments_tenant_id"),
        table_name="driver_vehicle_assignments",
    )
    op.create_index(
        op.f("ix_dva_vehicle"),
        "driver_vehicle_assignments",
        ["tenant_id", "vehicle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dva_tenant"), "driver_vehicle_assignments", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_dva_driver"),
        "driver_vehicle_assignments",
        ["tenant_id", "driver_id"],
        unique=False,
    )
