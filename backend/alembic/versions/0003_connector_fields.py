"""connector dedupe fields

Revision ID: 0003_connector_fields
Revises: 0002_signals_job_runs
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_connector_fields"
down_revision = "0002_signals_job_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("external_id", sa.String(length=140), nullable=True))
    op.add_column("opportunities", sa.Column("ingest_key", sa.String(length=64), nullable=True))
    op.create_index("ix_opportunities_ingest_key", "opportunities", ["ingest_key"])


def downgrade() -> None:
    op.drop_index("ix_opportunities_ingest_key", table_name="opportunities")
    op.drop_column("opportunities", "ingest_key")
    op.drop_column("opportunities", "external_id")
