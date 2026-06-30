"""baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "identities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("private_collection", sa.String(length=255), nullable=False),
        sa.Column("generation_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("retrieval_config_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_identities_workspace_slug"),
    )
    op.create_index(op.f("ix_identities_workspace_id"), "identities", ["workspace_id"])
    op.create_table(
        "provider_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("chat_provider", sa.String(length=64), nullable=False),
        sa.Column("chat_base_url", sa.String(length=512), nullable=True),
        sa.Column("chat_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("chat_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_base_url", sa.String(length=512), nullable=True),
        sa.Column("embedding_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("huggingface_endpoint", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_provider_configs_workspace"),
    )
    op.create_index(op.f("ix_provider_configs_workspace_id"), "provider_configs", ["workspace_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_workspace_id"), "users", ["workspace_id"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("identity_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_identity_id"), "conversations", ["identity_id"])
    op.create_index(op.f("ix_conversations_workspace_id"), "conversations", ["workspace_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("identity_id", sa.String(length=64), nullable=True),
        sa.Column("namespace", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "sha256",
            "namespace",
            "identity_id",
            name="uq_documents_workspace_hash_namespace_identity",
        ),
    )
    op.create_index(op.f("ix_documents_identity_id"), "documents", ["identity_id"])
    op.create_index(op.f("ix_documents_workspace_id"), "documents", ["workspace_id"])
    op.create_table(
        "index_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("namespace", sa.String(length=32), nullable=False),
        sa.Column("identity_id", sa.String(length=64), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["identity_id"], ["identities.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "collection_name", name="uq_index_versions_workspace_collection"),
    )
    op.create_index(op.f("ix_index_versions_identity_id"), "index_versions", ["identity_id"])
    op.create_index(op.f("ix_index_versions_workspace_id"), "index_versions", ["workspace_id"])
    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_jobs_document_id"), "ingest_jobs", ["document_id"])
    op.create_index(op.f("ix_ingest_jobs_workspace_id"), "ingest_jobs", ["workspace_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"])
    op.create_index(op.f("ix_messages_workspace_id"), "messages", ["workspace_id"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("index_version_id", sa.String(length=64), nullable=False),
        sa.Column("qdrant_point_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["index_version_id"], ["index_versions.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"])
    op.create_index(op.f("ix_document_chunks_index_version_id"), "document_chunks", ["index_version_id"])
    op.create_index(op.f("ix_document_chunks_workspace_id"), "document_chunks", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("messages")
    op.drop_table("ingest_jobs")
    op.drop_table("index_versions")
    op.drop_table("documents")
    op.drop_table("conversations")
    op.drop_table("users")
    op.drop_table("provider_configs")
    op.drop_table("identities")
    op.drop_table("workspaces")
