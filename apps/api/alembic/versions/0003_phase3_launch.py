"""Phase 3 launch hardening indexes and watchlist membership.

Revision ID: 0003_phase3_launch
Revises: 0002_phase2_enterprise
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_phase3_launch"
down_revision = "0002_phase2_enterprise"
branch_labels = None
depends_on = None


def _index_exists(table: str, name: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(index["name"] == name for index in inspector.get_indexes(table))


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "watchlist_items" not in inspector.get_table_names():
        op.create_table(
            "watchlist_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id"), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.String(length=120), nullable=False),
            sa.Column("label", sa.String(length=180), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("watchlist_id", "entity_type", "entity_id", name="uq_watchlist_entity"),
        )
    for table, name, columns in [
        ("watchlist_items", "ix_watchlist_items_organization_id", ["organization_id"]),
        ("watchlist_items", "ix_watchlist_items_watchlist_id", ["watchlist_id"]),
        ("alerts", "ix_alerts_org_status_severity", ["organization_id", "status", "severity"]),
        ("import_jobs", "ix_import_jobs_org_checksum_file", ["organization_id", "file_name"]),
        ("audit_events", "ix_audit_events_org_action_created", ["organization_id", "action", "created_at"]),
        ("query_plans", "ix_query_plans_org_intent", ["organization_id", "intent"]),
    ]:
        if table in inspect(op.get_bind()).get_table_names() and not _index_exists(table, name):
            op.create_index(name, table, columns, unique=False)


def downgrade() -> None:
    for table, name in [
        ("query_plans", "ix_query_plans_org_intent"),
        ("audit_events", "ix_audit_events_org_action_created"),
        ("import_jobs", "ix_import_jobs_org_checksum_file"),
        ("alerts", "ix_alerts_org_status_severity"),
        ("watchlist_items", "ix_watchlist_items_watchlist_id"),
        ("watchlist_items", "ix_watchlist_items_organization_id"),
    ]:
        if table in inspect(op.get_bind()).get_table_names() and _index_exists(table, name):
            op.drop_index(name, table_name=table)
    if "watchlist_items" in inspect(op.get_bind()).get_table_names():
        op.drop_table("watchlist_items")
