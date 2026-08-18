"""persona management

Revision ID: 0003_persona_management
Revises: 0002_reliability_fields
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_persona_management"
down_revision = "0002_reliability_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("identities") as batch:
        batch.add_column(sa.Column("avatar_url", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("identities") as batch:
        batch.drop_column("is_system")
        batch.drop_column("avatar_url")
