"""Make orchestration deployment creation idempotent and attributable."""

import sqlalchemy as sa
from alembic import op

revision = "0028_deployment_source_run"
down_revision = "0027_max_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deployments", sa.Column("source_run_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_deployments_source_run",
        "deployments",
        "orchestration_runs",
        ["source_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_deployments_source_run", "deployments", ["source_run_id"])


def downgrade() -> None:
    op.drop_constraint("uq_deployments_source_run", "deployments", type_="unique")
    op.drop_constraint("fk_deployments_source_run", "deployments", type_="foreignkey")
    op.drop_column("deployments", "source_run_id")
