"""Slides: one section per slide, so a chunk never mixes two slides.
Owner: Zuha replaces the body of chunk(), keeps the @register_chunker line."""
from app.ingestion.chunking.base import finish
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import by_slide, chunk_sections
from app.ingestion.contract import ChunkedDocument, ParsedDocument

NAME = "pptx-slides/1"     # saved with every chunk: raise the number whenever this chunker's output changes


@register_chunker("pptx")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, chunk_sections(doc, section_key=by_slide), NAME)