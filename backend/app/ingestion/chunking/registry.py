"""Which chunker handles which file type: the same pattern as the loader registry (app/ingestion/registry.py)."""
from collections.abc import Callable

from app.ingestion.contract import ChunkedDocument, ParsedDocument

Chunker = Callable[[ParsedDocument], ChunkedDocument]
_CHUNKERS: dict[str, Chunker] = {}


def register_chunker(*source_types: str) -> Callable[[Chunker], Chunker]:
    """Put @register_chunker("pdf") above a chunker's chunk() function."""
    def decorator(fn: Chunker) -> Chunker:
        for st in source_types:
            if st in _CHUNKERS and _CHUNKERS[st] is not fn:
                raise RuntimeError(f"two chunkers claim '{st}': {_CHUNKERS[st].__module__} and {fn.__module__}")
            _CHUNKERS[st] = fn
        return fn
    return decorator


def _load_all() -> None:
    import app.ingestion.chunking.chunkers  # noqa: F401  importing the package registers every chunker


def get_chunker(source_type: str) -> Chunker:
    _load_all()
    try:
        return _CHUNKERS[source_type]
    except KeyError:
        raise LookupError(f"no chunker registered for '{source_type}'") from None


def registered_chunkers() -> dict[str, Chunker]:
    _load_all()
    return dict(_CHUNKERS)