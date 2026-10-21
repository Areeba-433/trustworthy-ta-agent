"""PDF loader (owner: Minahil). Docling reads the book, to_blocks() makes blocks, restore_code_lines() gives code
listings their lines back, the book rules come next."""
from pathlib import Path

from app.ingestion import messages
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import ParsedDocument, PrecheckResult, ResourceMeta
from app.ingestion.converter import PARSER, PARSER_VERSION, convert
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.documents import parsed_document
from app.ingestion.pdf_code import restore_code_lines
from app.ingestion.registry import register
from app.ingestion.storage import Timer


@register("pdf", heavy=True)
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    timer = Timer()
    with timer("docling"):
        conversion = convert(path, "pdf", meta.file_sha256)
    if conversion.from_cache:              # say so, or a cached run looks like a very fast Docling
        timer.seconds["docling_cache"] = timer.seconds.pop("docling")
    title = title_from_filename(meta.file_name)
    with timer("blocks"):
        blocks = to_blocks(conversion.document, "pdf", title)
    with timer("code_lines"):
        blocks = restore_code_lines(blocks, conversion.document, path)
    problems, notes = page_findings(meta.precheck)
    doc = parsed_document(
        meta, title=title, blocks=blocks, parser=PARSER, parser_version=PARSER_VERSION,
        units_total=meta.precheck.pages_total, problems=[*conversion.problems, *problems], notes=notes,
    )
    doc.quality.seconds_taken.update(timer.seconds)
    return doc


def page_findings(pre: PrecheckResult) -> tuple[list[str], list[str]]:
    """What the pre-check found on single pages, as (problems, notes).

    Garbled text can lead to wrong answers: a problem. A picture-only page (often just the cover) holds nothing
    to search, and our scope is the text of digital files: a note.
    """
    problems = [messages.hard_to_read(pre.garbage_pages)] if pre.garbage_pages else []
    notes = [messages.no_text_units("Pages", pre.scanned_pages)] if pre.scanned_pages else []
    return problems, notes
