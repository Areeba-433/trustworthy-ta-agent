"""PDF books: the shared section chunker, with one book rule: a short introduction joins its first subsection
(join_intros). Owner: Minahil."""
from app.ingestion.chunking.base import finish
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.contract import ChunkedDocument, ParsedDocument

NAME = "pdf-sections/2"     # saved with every chunk: raise the number whenever this chunker's output changes


@register_chunker("pdf")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, chunk_sections(doc, join_intros=True), NAME)