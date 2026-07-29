from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chatmaster.db.base import Base
from chatmaster.db.models import Conversation, Identity, Message, Workspace
from chatmaster.identities.schema import IdentityConfig, RetrievalConfig
from chatmaster.retrieval.schemas import RetrievedChunk


def _identity() -> IdentityConfig:
    return IdentityConfig(
        id="legal_expert",
        name="法律专家",
        description="",
        system_prompt="请基于资料回答。",
        private_collection="chatmaster_legal_expert",
        retrieval=RetrievalConfig(top_k=2),
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        text="试用期不得违反劳动合同法。",
        source_file="劳动法试用期.txt",
        collection="chatmaster_legal_expert",
        rank=1,
        dense_score=0.91,
        fusion_score=0.02,
        metadata={"source_file": "劳动法试用期.txt"},
    )


@pytest.mark.asyncio
async def test_chat_service_emits_sources_before_tokens() -> None:
    from chatmaster.chat.graph import ChatRuntime
    from chatmaster.chat.service import stream_chat_events

    async def stream_answer(_state) -> AsyncIterator[str]:
        yield "答案"

    runtime = ChatRuntime(
        load_identity=lambda _identity_id: _identity(),
        load_history=lambda _conversation_id, _workspace_id, provided_history: provided_history,
        retrieve=lambda _identity, _message, _workspace_id: [_chunk()],
        stream_answer=stream_answer,
        persist=lambda _state: None,
    )

    events = [
        event
        async for event in stream_chat_events(
            identity_id="legal_expert",
            message="试用期多久？",
            history=[],
            conversation_id=None,
            workspace_id="local",
            user_id="local-user",
            runtime=runtime,
        )
    ]

    assert [event.type for event in events] == ["sources", "token", "done"]
    assert events[0].data["sources"][0]["source_file"] == "劳动法试用期.txt"
    assert events[1].data["delta"] == "答案"


@pytest.mark.asyncio
async def test_chat_graph_persists_messages_when_conversation_id_is_present() -> None:
    from chatmaster.chat.graph import ChatRuntime, persist_messages
    from chatmaster.chat.service import stream_chat_events

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
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
        db.add(
            Conversation(
                id="conversation-1",
                workspace_id="local",
                identity_id="identity-1",
                title="测试会话",
            )
        )
        db.commit()

    async def stream_answer(_state) -> AsyncIterator[str]:
        yield "持久化答案"

    def persist(state) -> None:
        with SessionLocal() as db:
            persist_messages(db, state)

    runtime = ChatRuntime(
        load_identity=lambda _identity_id: _identity(),
        load_history=lambda _conversation_id, _workspace_id, provided_history: provided_history,
        retrieve=lambda _identity, _message, _workspace_id: [_chunk()],
        stream_answer=stream_answer,
        persist=persist,
    )

    events = [
        event
        async for event in stream_chat_events(
            identity_id="legal_expert",
            message="请回答",
            history=[],
            conversation_id="conversation-1",
            workspace_id="local",
            user_id="local-user",
            runtime=runtime,
        )
    ]

    with SessionLocal() as db:
        messages = db.query(Message).order_by(Message.created_at).all()

    assert events[-1].type == "done"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].content == "持久化答案"
    assert messages[1].sources_json[0]["source_file"] == "劳动法试用期.txt"


@pytest.mark.asyncio
async def test_load_history_reads_messages_from_database() -> None:
    from chatmaster.chat.graph import _db_load_history

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with test_session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.add(
            Conversation(
                id="conversation-1",
                workspace_id="local",
                identity_id="legal_expert",
                title="历史",
            )
        )
        db.add(
            Message(
                id="message-1",
                workspace_id="local",
                conversation_id="conversation-1",
                role="user",
                content="第一条",
            )
        )
        db.add(
            Message(
                id="message-2",
                workspace_id="local",
                conversation_id="conversation-1",
                role="assistant",
                content="第二条",
            )
        )
        db.commit()

    import chatmaster.chat.graph as graph_module

    original = graph_module.SessionLocal
    graph_module.SessionLocal = test_session
    try:
        history = _db_load_history("conversation-1", "local", [])
    finally:
        graph_module.SessionLocal = original

    assert history == [
        {"role": "user", "content": "第一条"},
        {"role": "assistant", "content": "第二条"},
    ]


@pytest.mark.asyncio
async def test_chat_service_returns_error_event_for_unknown_identity() -> None:
    from chatmaster.chat.graph import ChatRuntime
    from chatmaster.chat.service import stream_chat_events

    def missing_identity(_identity_id: str):
        raise KeyError("missing")

    async def stream_answer(_state) -> AsyncIterator[str]:
        yield "should not stream"

    runtime = ChatRuntime(
        load_identity=missing_identity,
        load_history=lambda _conversation_id, _workspace_id, provided_history: provided_history,
        retrieve=lambda _identity, _message, _workspace_id: [],
        stream_answer=stream_answer,
        persist=lambda _state: None,
    )

    events = [
        event
        async for event in stream_chat_events(
            identity_id="missing",
            message="hello",
            history=[],
            conversation_id=None,
            workspace_id="local",
            user_id="local-user",
            runtime=runtime,
        )
    ]

    assert len(events) == 1
    assert events[0].type == "error"
    assert "missing" in events[0].data["detail"]


@pytest.mark.asyncio
async def test_durable_chat_turn_is_idempotent_and_returns_persisted_id(monkeypatch) -> None:
    from chatmaster.chat.graph import ChatRuntime
    from chatmaster.chat import service

    engine = create_engine("sqlite:///:memory:", future=True)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    with test_session() as db:
        db.add(Workspace(id="local", name="Local Workspace"))
        db.commit()

    async def stream_answer(_state) -> AsyncIterator[str]:
        yield "持久化"

    runtime = ChatRuntime(
        load_identity=lambda _identity_id: _identity(),
        load_history=lambda _conversation_id, _workspace_id, provided_history: provided_history,
        retrieve=lambda _identity, _message, _workspace_id: [_chunk()],
        stream_answer=stream_answer,
        persist=lambda _state: None,
    )
    monkeypatch.setattr(service, "SessionLocal", test_session)
    monkeypatch.setattr(service, "default_runtime", lambda: runtime)

    async def run_once():
        return [
            event
            async for event in service.stream_chat_events(
                request_id="request-1",
                identity_id="legal_expert",
                message="你好",
                history=[],
                conversation_id=None,
                workspace_id="local",
                user_id="local-user",
            )
        ]

    first = await run_once()
    conversation_id = first[-1].data["conversation_id"]
    second = [
        event
        async for event in service.stream_chat_events(
            request_id="request-1",
            identity_id="legal_expert",
            message="你好",
            history=[],
            conversation_id=conversation_id,
            workspace_id="local",
            user_id="local-user",
        )
    ]

    with test_session() as db:
        messages = list(db.query(Message).order_by(Message.created_at))
    assert len(messages) == 2
    assert first[-1].data["message_id"] == messages[1].id
    assert second[-1].data["message_id"] == messages[1].id
    assert messages[1].status == "complete"


@pytest.mark.asyncio
async def test_chat_cancel_finishes_with_stopped_status() -> None:
    from chatmaster.chat.graph import ChatRuntime
    from chatmaster.chat.service import request_cancel, stream_chat_events

    async def stream_answer(_state) -> AsyncIterator[str]:
        yield "一"
        yield "二"

    runtime = ChatRuntime(
        load_identity=lambda _identity_id: _identity(),
        load_history=lambda _conversation_id, _workspace_id, provided_history: provided_history,
        retrieve=lambda _identity, _message, _workspace_id: [],
        stream_answer=stream_answer,
        persist=lambda _state: None,
    )
    stream = stream_chat_events(
        request_id="request-stop",
        identity_id="legal_expert",
        message="停止",
        history=[],
        conversation_id=None,
        workspace_id="local",
        user_id="local-user",
        runtime=runtime,
    )
    events = [await anext(stream), await anext(stream)]
    assert request_cancel("request-stop") is True
    events.extend([event async for event in stream])
    assert events[-1].type == "done"
    assert events[-1].data["status"] == "stopped"
