from collections.abc import Callable
from pathlib import Path

from app.ingestion.contract import ParsedDocument, ResourceMeta

Loader = Callable[[Path, ResourceMeta], ParsedDocument]
_LOADERS: dict[str, Loader] = {}


def register(*source_types: str) -> Callable[[Loader], Loader]:
    """Put @register("pdf", "docx", "pptx") above a loader's load() function."""
    def decorator(fn: Loader) -> Loader:
        for st in source_types:
            if st in _LOADERS and _LOADERS[st] is not fn:
                raise RuntimeError(f"two loaders claim '{st}': {_LOADERS[st].__module__} and {fn.__module__}")
            _LOADERS[st] = fn
        return fn
    return decorator


def _load_all() -> None:
    import app.ingestion.loaders  # noqa: F401  importing the package registers every loader


def get_loader(source_type: str) -> Loader:
    _load_all()
    try:
        return _LOADERS[source_type]
    except KeyError:
        raise LookupError(f"no loader registered for '{source_type}'") from None


def registered() -> dict[str, Loader]:
    _load_all()
    return dict(_LOADERS)