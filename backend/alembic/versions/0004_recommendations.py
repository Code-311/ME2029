"""recommendations

Revision ID: 0004_recommendations
Revises: 0003_company_signals
Create Date: 2026-03-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_recommendations"
down_revision = "0003_company_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_type", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("decision_score", sa.Float(), nullable=False),
        sa.Column("urgency", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason_summary", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_index("ix_recommendations_recommendation_type", "recommendations", ["recommendation_type"])
    op.create_index("ix_recommendations_entity_type", "recommendations", ["entity_type"])
    op.create_index("ix_recommendations_entity_id", "recommendations", ["entity_id"])
    op.create_index("ix_recommendations_urgency", "recommendations", ["urgency"])
    op.create_index("ix_recommendations_status", "recommendations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_index("ix_recommendations_urgency", table_name="recommendations")
    op.drop_index("ix_recommendations_entity_id", table_name="recommendations")
    op.drop_index("ix_recommendations_entity_type", table_name="recommendations")
    op.drop_index("ix_recommendations_recommendation_type", table_name="recommendations")
    op.drop_table("recommendations")
