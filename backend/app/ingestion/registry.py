"""Loaders register themselves here; the dispatcher looks them up. Owner: Minahil.

A track adds a format by decorating its own load() function, so nobody edits
the dispatcher:

    @register("pdf", "docx", "pptx")
    def load(path: Path, meta: ResourceMeta) -> ParsedDocument: ...
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from app.ingestion.contract import SOURCE_TYPES, ParsedDocument, ResourceMeta

Loader = Callable[[Path, ResourceMeta], ParsedDocument]

_LOADERS: dict[str, Loader] = {}


def _name(fn: Loader) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


def register(*source_types: str) -> Callable[[Loader], Loader]:
    """Mark a function as THE loader for these source types (one track per type)."""
    def decorator(fn: Loader) -> Loader:
        for source_type in source_types:
            if source_type not in SOURCE_TYPES:
                raise ValueError(f"{source_type!r} is not a SourceType in contract.py")
            existing = _LOADERS.get(source_type)
            if existing is not None and _name(existing) != _name(fn):
                raise ValueError(
                    f"{source_type!r} is already handled by {_name(existing)}; "
                    "each source type belongs to exactly one track")
            _LOADERS[source_type] = fn
        return fn
    return decorator


def _import_all_loaders() -> None:
    importlib.import_module("app.ingestion.loaders")  # runs every track's @register


def get_loader(source_type: str) -> Loader:
    _import_all_loaders()
    try:
        return _LOADERS[source_type]
    except KeyError:
        from app.ingestion.loaders import MISSING
        raise LookupError(
            f"No loader is registered for {source_type!r}. Tracks that failed to load: "
            f"{MISSING or 'none'}") from None


def registered() -> dict[str, str]:
    """{source_type: "module.function"} for every registered loader."""
    _import_all_loaders()
    return {source_type: _name(fn) for source_type, fn in sorted(_LOADERS.items())}
