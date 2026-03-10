"""company signals

Revision ID: 0003_company_signals
Revises: 0002_signals_job_runs
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_company_signals"
down_revision = "0002_signals_job_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("signal_type", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_company_signals_company_id", "company_signals", ["company_id"])
    op.create_index("ix_company_signals_signal_type", "company_signals", ["signal_type"])
    op.create_index("ix_company_signals_detected_at", "company_signals", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_company_signals_detected_at", table_name="company_signals")
    op.drop_index("ix_company_signals_signal_type", table_name="company_signals")
    op.drop_index("ix_company_signals_company_id", table_name="company_signals")
    op.drop_table("company_signals")
