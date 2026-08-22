"""add_route_optimization

Revision ID: opt01
Revises: cat02
Create Date: 2026-07-25 00:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "opt01"
down_revision: str | None = "cat02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("route_geometry", postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column("trips", sa.Column("route_polyline", sa.Text(), nullable=True))
    op.add_column("trips", sa.Column("route_distance_km", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("trips", sa.Column("route_duration_seconds", sa.Integer(), nullable=True))

    op.add_column("trip_stops", sa.Column("sequence_number", sa.Integer(), nullable=True, server_default="0"))

    op.add_column("known_routes", sa.Column("destination_lat", sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column("known_routes", sa.Column("destination_lon", sa.Numeric(precision=9, scale=6), nullable=True))


def downgrade() -> None:
    op.drop_column("known_routes", "destination_lon")
    op.drop_column("known_routes", "destination_lat")
    op.drop_column("trip_stops", "sequence_number")
    op.drop_column("trips", "route_duration_seconds")
    op.drop_column("trips", "route_distance_km")
    op.drop_column("trips", "route_polyline")
    op.drop_column("trips", "route_geometry")
