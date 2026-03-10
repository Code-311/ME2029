"""connector keys

Revision ID: 0003_connector_keys
Revises: 0002_signals_job_runs
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_connector_keys"
down_revision = "0002_signals_job_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("external_id", sa.String(length=160), nullable=False, server_default=""))
    op.add_column("opportunities", sa.Column("ingestion_key", sa.String(length=255), nullable=False, server_default=""))
    op.create_index("ix_opportunities_ingestion_key", "opportunities", ["ingestion_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_opportunities_ingestion_key", table_name="opportunities")
    op.drop_column("opportunities", "ingestion_key")
    op.drop_column("opportunities", "external_id")
