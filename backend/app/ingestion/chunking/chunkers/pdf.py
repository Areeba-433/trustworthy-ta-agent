"""PDF books, notes and slides: the shared section chunker with three PDF rules (owner: Minahil):
- join_intros: a short introduction joins its first subsection;
- share_figures: a figure that ends a chunk also starts the next chunk on its page, so a screenshot is never
  separated from the paragraph under it that explains it;
- name_pieces: the later pieces of a long listing start with "// shapes.cpp (continued)"."""
from app.ingestion.chunking.base import finish
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.contract import ChunkedDocument, ParsedDocument

NAME = "pdf-sections/3"     # saved with every chunk: raise the number whenever this chunker's output changes


@register_chunker("pdf")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    return finish(doc, chunk_sections(doc, join_intros=True, share_figures=True, name_pieces=True), NAME)
