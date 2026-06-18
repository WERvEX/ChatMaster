"""Load and validate identity configs from identities.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from chatmaster.identities.schema import IdentityConfig, IdentityOut

YAML_PATH = Path(__file__).parent / "identities.yaml"


class IdentityNotFound(KeyError):
    """Raised when a requested identity id does not exist."""


class IdentityRegistry:
    """Holds validated identity configs, keyed by id."""

    def __init__(self, identities: list[IdentityConfig]) -> None:
        self._by_id: dict[str, IdentityConfig] = {i.id: i for i in identities}

    def list_all(self) -> list[IdentityConfig]:
        return list(self._by_id.values())

    def list_public(self) -> list[IdentityOut]:
        settings = _settings()
        return [
            IdentityOut(
                id=i.id,
                name=i.name,
                description=i.description,
                generation_model=i.generation_model or settings.default_generation_model,
                retrieval=i.retrieval,
            )
            for i in self._by_id.values()
        ]

    def get(self, identity_id: str) -> IdentityConfig:
        try:
            return self._by_id[identity_id]
        except KeyError:
            raise IdentityNotFound(identity_id) from None

    def all_collections(self) -> list[str]:
        """All private collections (common collection added separately by caller)."""
        return [i.private_collection for i in self._by_id.values()]


def _settings():
    # Imported lazily to avoid a circular import at module load time.
    from chatmaster.config import get_settings

    return get_settings()


def load_registry(path: Path = YAML_PATH) -> IdentityRegistry:
    """Read YAML, validate every entry, fail fast on errors."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = raw.get("identities") if isinstance(raw, dict) else None
    if not items:
        raise ValueError(f"No identities found in {path}")

    identities = [IdentityConfig(**item) for item in items]

    # Duplicate id guard
    seen: set[str] = set()
    for ident in identities:
        if ident.id in seen:
            raise ValueError(f"Duplicate identity id: {ident.id}")
        seen.add(ident.id)

    return IdentityRegistry(identities)


@lru_cache
def get_registry() -> IdentityRegistry:
    return load_registry()


def reload_registry() -> IdentityRegistry:
    get_registry.cache_clear()
    return get_registry()
