"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_profiles", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("full_name", sa.String(120), nullable=False), sa.Column("headline", sa.String(200), nullable=False), sa.Column("leadership_scale", sa.Integer(), nullable=False), sa.Column("skills", sa.Text(), nullable=False), sa.Column("preferred_geographies", sa.Text(), nullable=False), sa.Column("compensation_threshold", sa.Float(), nullable=False), sa.Column("industry_preferences", sa.Text(), nullable=False), sa.Column("target_time_horizon", sa.String(80), nullable=False), sa.Column("networking_style", sa.String(120), nullable=False), sa.Column("visibility_preferences", sa.String(120), nullable=False))
    op.create_table("companies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(140), unique=True, nullable=False), sa.Column("industry", sa.String(120), nullable=False))
    op.create_table("opportunities", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company", sa.String(120), nullable=False), sa.Column("role_title", sa.String(160), nullable=False), sa.Column("location", sa.String(120), nullable=False), sa.Column("estimated_compensation", sa.Float(), nullable=False), sa.Column("source", sa.String(80), nullable=False), sa.Column("source_url", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("discovered_at", sa.DateTime(), nullable=False), sa.Column("status", sa.String(80), nullable=False), sa.Column("notes", sa.Text(), nullable=False), sa.Column("score_total", sa.Float(), nullable=False), sa.Column("score_breakdown", sa.Text(), nullable=False), sa.Column("score_explanation", sa.Text(), nullable=False), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True))
    op.create_table("person_nodes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("full_name", sa.String(140), nullable=False), sa.Column("role_title", sa.String(120), nullable=False), sa.Column("node_role_type", sa.String(80), nullable=False), sa.Column("influence_score", sa.Float(), nullable=False), sa.Column("accessibility_score", sa.Float(), nullable=False), sa.Column("relationship_strength", sa.Float(), nullable=False), sa.Column("connection_path", sa.String(255), nullable=False), sa.Column("notes_history", sa.Text(), nullable=False), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False), sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunities.id"), nullable=True))
    op.create_table("action_plan_items", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("period_type", sa.String(20), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("details", sa.Text(), nullable=False), sa.Column("due_label", sa.String(60), nullable=False), sa.Column("completed", sa.Boolean(), nullable=False), sa.Column("opportunity_id", sa.Integer(), nullable=True))
    op.create_table("scoring_weights", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(80), unique=True, nullable=False), sa.Column("value", sa.Float(), nullable=False))
    op.create_table("feature_flags", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(80), unique=True, nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False))


def downgrade() -> None:
    for t in ["feature_flags", "scoring_weights", "action_plan_items", "person_nodes", "opportunities", "companies", "user_profiles"]:
        op.drop_table(t)
