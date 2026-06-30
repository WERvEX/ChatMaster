"""Schemas used by retrieval and ranking services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document


@dataclass(frozen=True)
class SearchHit:
    document: Document
    collection: str
    rank: int
    dense_score: float | None


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source_file: str
    collection: str
    rank: int
    dense_score: float | None
    fusion_score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.fusion_score

