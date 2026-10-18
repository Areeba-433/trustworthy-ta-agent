"""PDF books: the shared section chunker for now; book-specific rules come with the PDF loader.
Owner: Minahil replaces the body of chunk(), keeps the @register_chunker line."""
from app.ingestion.chunking.base import finish
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.contract import ChunkedDocument, ParsedDocument

NAME = "pdf-sections/1"     # saved with every chunk: raise the number whenever this chunker's output changes


@register_chunker("pdf")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, chunk_sections(doc), NAME)