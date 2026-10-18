"""Lecture recordings: each transcript window from the loader is its own section, so windows never merge.
Owner: Zuha replaces the body of chunk(), keeps the @register_chunker line."""
from app.ingestion.chunking.base import finish
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.contract import Block, ChunkedDocument, ParsedDocument

NAME = "audio-windows/1"     # saved with every chunk: raise the number whenever this chunker's output changes


def _by_window(block: Block) -> int:
    return block.seq


@register_chunker("audio")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, chunk_sections(doc, section_key=_by_window), NAME)