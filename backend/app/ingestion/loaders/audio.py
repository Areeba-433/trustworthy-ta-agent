"""Placeholder. Owner: Zoha replaces the body of load(), keeps the @register line."""
from pathlib import Path

from app.ingestion.contract import ParsedDocument, ResourceMeta
from app.ingestion.loaders._stub import stub_document
from app.ingestion.registry import register


@register("audio")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    return stub_document(meta, kind="audio")