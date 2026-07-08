"""Phase 2 enterprise tenancy and operational-query index.

The Phase 1 bootstrap migration intentionally uses metadata creation for the local reference
implementation. This revision adds the Phase 2 query index used by tenant-scoped execution.
"""
from alembic import op

revision = "0002_phase2_enterprise"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_ai_executions_org_status", "ai_query_executions", ["organization_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_executions_org_status", table_name="ai_query_executions")
