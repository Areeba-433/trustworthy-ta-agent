"""Word files: the shared section chunker, one section per heading.
Owner: Areeba replaces the body of chunk(), keeps the @register_chunker line."""
from app.ingestion.chunking.base import Draft, finish, merge_locations
from app.ingestion.chunking.registry import register_chunker
from app.ingestion.chunking.sections import chunk_sections
from app.ingestion.chunking.split import split_to_fit
from app.ingestion.chunking.tokens import count_tokens
from app.ingestion.contract import MAX_CHUNK_TOKENS, ChunkedDocument, ParsedDocument

NAME = "docx-sections/2"     # saved with every chunk: raise the number whenever this chunker's output changes


@register_chunker("docx")
def chunk(doc: ParsedDocument) -> ChunkedDocument:
    drafts = chunk_sections(doc)
    if not drafts:
        drafts = _headings_only(doc)
    return finish(doc, drafts, NAME)


def _headings_only(doc: ParsedDocument) -> list[Draft]:
    """A file of headings and nothing else (an outline): its headings become the text.

    chunk_sections() keeps headings out of chunk text (they travel in heading_path), which leaves such a file
    with no chunk at all, and the upload failed with "Something went wrong". Its headings are its content.
    """
    headings = [b for b in doc.blocks if b.kind == "heading"]
    if not headings:
        return []
    text = "\n".join(b.text for b in headings)
    loc = merge_locations([b.loc for b in headings])
    return [Draft(text=piece, heading_path=[doc.title], loc=loc, kinds=["heading"],
                  block_seqs=[b.seq for b in headings])
            for piece in split_to_fit(text, "paragraph", MAX_CHUNK_TOKENS, count_tokens)]