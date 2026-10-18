from collections.abc import Callable
from pathlib import Path

from app.ingestion.contract import ParsedDocument, ResourceMeta

Loader = Callable[[Path, ResourceMeta], ParsedDocument]
_LOADERS: dict[str, Loader] = {}
_HEAVY: set[str] = set()        # file types whose loader needs a lot of memory


def register(*source_types: str, heavy: bool = False) -> Callable[[Loader], Loader]:
    """Put @register("pdf") above a loader's load() function.

    heavy=True: the loader runs big models (Docling), so the dispatcher lets only one such file load at a time.
    """
    def decorator(fn: Loader) -> Loader:
        for st in source_types:
            if st in _LOADERS and _LOADERS[st] is not fn:
                raise RuntimeError(f"two loaders claim '{st}': {_LOADERS[st].__module__} and {fn.__module__}")
            _LOADERS[st] = fn
            if heavy:
                _HEAVY.add(st)
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


def is_heavy(source_type: str) -> bool:
    _load_all()
    return source_type in _HEAVY


def registered() -> dict[str, Loader]:
    _load_all()
    return dict(_LOADERS)