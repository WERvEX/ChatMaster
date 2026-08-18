"""LangGraph workflow and runtime dependencies for chat."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from chatmaster.ai.models import build_chat_model, build_embeddings
from chatmaster.ai.prompts import build_prompt, format_context
from chatmaster.conversations.service import load_history as load_history_from_db
from chatmaster.db.models import Conversation, Message, utc_now
from chatmaster.db.session import SessionLocal
from chatmaster.identities.schema import IdentityConfig
from chatmaster.identities.service import get_identity_config
from chatmaster.retrieval.retriever import retrieve
from chatmaster.retrieval.schemas import RetrievedChunk

from .state import ChatState


def history_to_messages(history: list[dict[str, str]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in history:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages


def chunks_to_sources(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "n": index,
            "source_file": chunk.source_file,
            "collection": chunk.collection,
            "score": round(chunk.fusion_score, 6),
            "dense_score": chunk.dense_score,
            "rank": chunk.rank,
            "document_id": chunk.metadata.get("document_id"),
            "chunk_id": chunk.metadata.get("chunk_id") or chunk.metadata.get("_id"),
        }
        for index, chunk in enumerate(chunks, start=1)
    ]


async def default_stream_answer(state: ChatState) -> AsyncIterator[str]:
    identity = state["identity"]
    chat_model = build_chat_model(identity)
    async for chunk in chat_model.astream(state["messages"]):
        token = chunk.content if isinstance(chunk.content, str) else ""
        if token:
            yield token


@dataclass
class ChatRuntime:
    load_identity: Callable[[str], IdentityConfig]
    load_history: Callable[[str | None, str, list[dict[str, str]]], list[dict[str, str]]]
    retrieve: Callable[[IdentityConfig, str, str], list[RetrievedChunk] | Any]
    stream_answer: Callable[[ChatState], AsyncIterator[str]]
    persist: Callable[[ChatState], None]


def _db_load_history(
    conversation_id: str | None,
    workspace_id: str,
    provided_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not conversation_id:
        return provided_history
    with SessionLocal() as db:
        return load_history_from_db(db, workspace_id=workspace_id, conversation_id=conversation_id)


def default_runtime() -> ChatRuntime:
    async def retrieve_chunks(
        identity: IdentityConfig, message: str, workspace_id: str
    ) -> list[RetrievedChunk]:
        embeddings = build_embeddings(identity)
        with SessionLocal() as db:
            return await retrieve(identity, message, embeddings, db=db, workspace_id=workspace_id)

    return ChatRuntime(
        load_identity=lambda identity_id: get_identity_config(identity_id),
        load_history=_db_load_history,
        retrieve=retrieve_chunks,
        stream_answer=default_stream_answer,
        persist=lambda _state: None,
    )


def build_chat_graph(runtime: ChatRuntime):
    graph = StateGraph(ChatState)

    def load_identity_node(state: ChatState) -> ChatState:
        return {"identity": runtime.load_identity(state["identity_id"])}

    def load_history_node(state: ChatState) -> ChatState:
        return {
            "history": runtime.load_history(
                state.get("conversation_id"),
                state["workspace_id"],
                state.get("history", []),
            )
        }

    async def retrieve_context_node(state: ChatState) -> ChatState:
        result = runtime.retrieve(state["identity"], state["message"], state["workspace_id"])
        chunks = await result if hasattr(result, "__await__") else result
        return {
            "retrieved_chunks": chunks,
            "sources": chunks_to_sources(chunks),
        }

    def build_messages_node(state: ChatState) -> ChatState:
        identity = state["identity"]
        prompt = build_prompt(identity.system_prompt)
        messages = prompt.format_messages(
            system_prompt=identity.system_prompt,
            context=format_context(state.get("retrieved_chunks", [])),
            history=history_to_messages(state.get("history", [])),
            message=state["message"],
        )
        return {"messages": messages}

    graph.add_node("load_identity", load_identity_node)
    graph.add_node("load_history", load_history_node)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("build_messages", build_messages_node)

    graph.set_entry_point("load_identity")
    graph.add_edge("load_identity", "load_history")
    graph.add_edge("load_history", "retrieve_context")
    graph.add_edge("retrieve_context", "build_messages")
    graph.add_edge("build_messages", END)
    return graph.compile()


async def prepare_chat_state(runtime: ChatRuntime, state: ChatState) -> ChatState:
    graph = build_chat_graph(runtime)
    return await graph.ainvoke(state)


def persist_messages(db: Session, state: ChatState) -> None:
    conversation_id = state.get("conversation_id")
    if not conversation_id:
        return

    user_message = Message(
        id=str(uuid.uuid4()),
        workspace_id=state["workspace_id"],
        conversation_id=conversation_id,
        role="user",
        content=state["message"],
        sources_json=None,
        request_id=state.get("request_id"),
        status="complete",
    )
    assistant_message = Message(
        id=str(uuid.uuid4()),
        workspace_id=state["workspace_id"],
        conversation_id=conversation_id,
        role="assistant",
        content=state.get("answer", ""),
        sources_json=state.get("sources", []),
        request_id=state.get("request_id"),
        status=state.get("status", "complete"),
    )
    db.add_all([user_message, assistant_message])
    conversation = db.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = utc_now()
    db.commit()
