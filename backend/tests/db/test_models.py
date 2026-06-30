from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import (
    Conversation,
    Document,
    DocumentChunk,
    Identity,
    IndexVersion,
    IngestJob,
    Message,
    ProviderConfig,
    User,
    Workspace,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as session:
        yield session


def test_business_models_can_persist_core_local_workspace_graph(db: Session) -> None:
    workspace = Workspace(id="local", name="Local Workspace")
    user = User(id="local-user", workspace_id=workspace.id, email=None, display_name="Local User")
    identity = Identity(
        id="identity-1",
        workspace_id=workspace.id,
        slug="legal_expert",
        name="法律专家",
        description="中国法律咨询专家",
        system_prompt="请基于参考资料回答。",
        private_collection="chatmaster_legal_expert",
        generation_model="deepseek-v4-pro",
        embedding_model="BAAI/bge-small-zh-v1.5",
        retrieval_config_json={"top_k": 6, "private_weight": 0.7, "common_weight": 0.3},
    )
    provider = ProviderConfig(
        id="provider-1",
        workspace_id=workspace.id,
        chat_provider="openai",
        chat_base_url="https://api.deepseek.com/v1",
        chat_api_key_encrypted="sk-test",
        chat_model="deepseek-v4-pro",
        embedding_provider="huggingface",
        embedding_base_url=None,
        embedding_api_key_encrypted=None,
        embedding_model="BAAI/bge-small-zh-v1.5",
        huggingface_endpoint="https://hf-mirror.com",
    )
    conversation = Conversation(
        id="conversation-1",
        workspace_id=workspace.id,
        identity_id=identity.id,
        title="劳动法咨询",
    )
    user_message = Message(
        id="message-user-1",
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        role="user",
        content="试用期最长多久？",
    )
    assistant_message = Message(
        id="message-assistant-1",
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        role="assistant",
        content="需要结合劳动合同期限判断。",
        sources_json=[{"n": 1, "source_file": "劳动法试用期.txt"}],
    )
    document = Document(
        id="document-1",
        workspace_id=workspace.id,
        identity_id=identity.id,
        namespace="private",
        filename="劳动法试用期.txt",
        content_type="text/plain",
        storage_path="data/storage/local/documents/document-1/劳动法试用期.txt",
        sha256="a" * 64,
        status="indexed",
    )
    index_version = IndexVersion(
        id="index-version-1",
        workspace_id=workspace.id,
        namespace="private",
        identity_id=identity.id,
        collection_name="chatmaster_legal_expert",
        embedding_provider="huggingface",
        embedding_model="BAAI/bge-small-zh-v1.5",
        embedding_dim=512,
        status="active",
    )
    chunk = DocumentChunk(
        id="chunk-1",
        workspace_id=workspace.id,
        document_id=document.id,
        index_version_id=index_version.id,
        qdrant_point_id="point-1",
        chunk_index=0,
        text="同一用人单位与同一劳动者只能约定一次试用期。",
        metadata_json={"page": 1},
    )
    job = IngestJob(
        id="job-1",
        workspace_id=workspace.id,
        document_id=document.id,
        status="completed",
        error=None,
        total_chunks=1,
    )

    db.add_all(
        [
            workspace,
            user,
            identity,
            provider,
            conversation,
            user_message,
            assistant_message,
            document,
            index_version,
            chunk,
            job,
        ]
    )
    db.commit()

    saved_conversation = db.get(Conversation, "conversation-1")
    saved_document = db.get(Document, "document-1")

    assert saved_conversation is not None
    assert saved_conversation.identity_id == "identity-1"
    assert saved_document is not None
    assert saved_document.chunks[0].qdrant_point_id == "point-1"
    assert saved_document.ingest_jobs[0].status == "completed"


def test_identity_slug_is_unique_inside_workspace(db: Session) -> None:
    db.add(Workspace(id="local", name="Local Workspace"))
    db.add(
        Identity(
            id="identity-1",
            workspace_id="local",
            slug="legal_expert",
            name="法律专家",
            description="",
            system_prompt="",
            private_collection="chatmaster_legal_expert",
        )
    )
    db.commit()

    db.add(
        Identity(
            id="identity-2",
            workspace_id="local",
            slug="legal_expert",
            name="另一个法律专家",
            description="",
            system_prompt="",
            private_collection="chatmaster_legal_expert_2",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()
