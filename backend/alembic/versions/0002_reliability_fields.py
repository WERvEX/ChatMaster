"""reliability fields

Revision ID: 0002_reliability_fields
Revises: 0001_baseline
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_reliability_fields"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("request_id", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(length=32), nullable=False, server_default="complete")
        )
        batch.create_index("ix_messages_request_id", ["request_id"])
        batch.create_unique_constraint(
            "uq_messages_conversation_request_role",
            ["conversation_id", "request_id", "role"],
        )

    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column("scope_key", sa.String(length=128), nullable=False, server_default="common")
        )
    op.execute(
        "UPDATE documents SET scope_key = "
        "CASE WHEN namespace = 'common' THEN 'common' ELSE identity_id END"
    )
    with op.batch_alter_table("documents") as batch:
        batch.create_unique_constraint(
            "uq_documents_workspace_hash_scope",
            ["workspace_id", "sha256", "scope_key"],
        )

    with op.batch_alter_table("index_versions") as batch:
        batch.add_column(
            sa.Column("logical_name", sa.String(length=255), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column(
                "config_fingerprint",
                sa.String(length=64),
                nullable=False,
                server_default="legacy",
            )
        )
    op.execute("UPDATE index_versions SET logical_name = collection_name WHERE logical_name = ''")

    with op.batch_alter_table("document_chunks") as batch:
        batch.create_unique_constraint(
            "uq_document_chunks_version_document_index",
            ["index_version_id", "document_id", "chunk_index"],
        )


def downgrade() -> None:
    with op.batch_alter_table("document_chunks") as batch:
        batch.drop_constraint(
            "uq_document_chunks_version_document_index",
            type_="unique",
        )
    with op.batch_alter_table("index_versions") as batch:
        batch.drop_column("config_fingerprint")
        batch.drop_column("logical_name")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_documents_workspace_hash_scope", type_="unique")
        batch.drop_column("scope_key")
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("uq_messages_conversation_request_role", type_="unique")
        batch.drop_index("ix_messages_request_id")
        batch.drop_column("status")
        batch.drop_column("request_id")
