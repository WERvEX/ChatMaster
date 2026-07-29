"""Chat prompt templates — system prompt + a ## 参考资料 context block with
citation markers, plus the conversation history and user input."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from chatmaster.retrieval.schemas import RetrievedChunk

CONTEXT_HEADER = "## 参考资料\n请基于以下参考资料回答用户问题，并在合适处标注引用序号 [n]："


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as a numbered, source-tagged context block."""
    if not chunks:
        return "（本次未检索到相关参考资料，请基于你的专业知识谨慎作答。）"
    lines = [CONTEXT_HEADER]
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] (来源: {c.source_file} / {c.collection})\n{c.text}")
    return "\n\n".join(lines)


def build_prompt(system_prompt: str) -> ChatPromptTemplate:
    """Prompt with: system (persona + context), history, user message."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}\n\n{context}"),
            MessagesPlaceholder("history"),
            ("human", "{message}"),
        ]
    )
