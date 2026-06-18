"""harden core integrity constraints

Revision ID: f4c8a12d9b30
Revises: c7d8e9f0a1b2
Create Date: 2026-06-18
"""

from alembic import op

revision: str = "f4c8a12d9b30"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


CHECKS: tuple[tuple[str, str, str], ...] = (
    ("vehicles", "chk_vehicles_current_km_non_negative", "current_km >= 0"),
    (
        "vehicles",
        "chk_vehicles_max_payload_non_negative",
        "max_payload_kg IS NULL OR max_payload_kg >= 0",
    ),
    ("drivers", "chk_drivers_score_range", "score >= 0 AND score <= 100"),
    ("trips", "chk_trips_km_start_non_negative", "km_start IS NULL OR km_start >= 0"),
    ("trips", "chk_trips_km_end_non_negative", "km_end IS NULL OR km_end >= 0"),
    (
        "trips",
        "chk_trips_km_end_gte_start",
        "km_start IS NULL OR km_end IS NULL OR km_end >= km_start",
    ),
    (
        "trips",
        "chk_trips_cargo_weight_non_negative",
        "cargo_weight IS NULL OR cargo_weight >= 0",
    ),
    (
        "trips",
        "chk_trips_cargo_volume_non_negative",
        "cargo_volume IS NULL OR cargo_volume >= 0",
    ),
    (
        "trips",
        "chk_trips_cargo_volumes_non_negative",
        "cargo_volumes IS NULL OR cargo_volumes >= 0",
    ),
    ("trips", "chk_trips_total_fuel_cost_non_negative", "total_fuel_cost >= 0"),
    ("trips", "chk_trips_total_expense_cost_non_negative", "total_expense_cost >= 0"),
    ("trips", "chk_trips_total_transport_cost_non_negative", "total_transport_cost >= 0"),
    ("trips", "chk_trips_actual_revenue_non_negative", "actual_revenue >= 0"),
    ("fuel_logs", "chk_fuel_logs_liters_positive", "liters > 0"),
    ("fuel_logs", "chk_fuel_logs_total_cost_non_negative", "total_cost >= 0"),
    ("fuel_logs", "chk_fuel_logs_km_at_refuel_non_negative", "km_at_refuel >= 0"),
    (
        "fuel_logs",
        "chk_fuel_logs_km_since_last_non_negative",
        "km_since_last IS NULL OR km_since_last >= 0",
    ),
    (
        "fuel_logs",
        "chk_fuel_logs_consumption_non_negative",
        "consumption_l_per_100km IS NULL OR consumption_l_per_100km >= 0",
    ),
    ("billing_documents", "chk_billing_documents_subtotal_non_negative", "subtotal >= 0"),
    ("billing_documents", "chk_billing_documents_tax_non_negative", "tax_amount >= 0"),
    ("billing_documents", "chk_billing_documents_total_non_negative", "total_amount >= 0"),
    (
        "billing_documents",
        "chk_billing_documents_iva_rate_range",
        "iva_rate IS NULL OR (iva_rate >= 0 AND iva_rate <= 1)",
    ),
    (
        "billing_items",
        "chk_billing_items_quantity_non_negative",
        "quantity IS NULL OR quantity >= 0",
    ),
    (
        "billing_items",
        "chk_billing_items_unit_price_non_negative",
        "unit_price IS NULL OR unit_price >= 0",
    ),
    ("billing_items", "chk_billing_items_amount_non_negative", "amount >= 0"),
    (
        "billing_items",
        "chk_billing_items_iva_rate_range",
        "iva_rate IS NULL OR (iva_rate >= 0 AND iva_rate <= 1)",
    ),
    (
        "billing_items",
        "chk_billing_items_iva_amount_non_negative",
        "iva_amount IS NULL OR iva_amount >= 0",
    ),
)


def _add_check_not_valid(table_name: str, constraint_name: str, expression: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{constraint_name}'
            ) THEN
                ALTER TABLE {table_name}
                ADD CONSTRAINT {constraint_name}
                CHECK ({expression}) NOT VALID;
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    for table_name, constraint_name, expression in CHECKS:
        _add_check_not_valid(table_name, constraint_name, expression)


def downgrade() -> None:
    for table_name, constraint_name, _expression in reversed(CHECKS):
        op.execute(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}")
