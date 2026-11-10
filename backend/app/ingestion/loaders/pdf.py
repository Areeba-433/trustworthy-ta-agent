"""PDF loader (owner: Minahil). Docling reads the book. On Docling's result: remove_chapter_tabs() takes the decoration
on the page edges out, remove_contents_and_index() the contents and index pages, link_figure_labels() gives a
picture the "FIGURE 2.3" label Docling read as a heading or left loose, join_caption_lines() gives a caption back
its description line, and split_long_headings() cuts a heading Docling made of a whole region
back to the heading. Then to_blocks() makes blocks, restore_code_lines() gives code listings their lines back and
tells code from sentences by font, mark_exponents() keeps the exponent of a power of ten ("10^308"),
order_by_position() puts what stands higher on a page first, and mark_figures() notes where each figure is, so an
answer can show it."""
from pathlib import Path

from app.ingestion import messages
from app.ingestion.cleaning.common import title_from_filename
from app.ingestion.contract import ParsedDocument, PrecheckResult, ResourceMeta
from app.ingestion.converter import PARSER, PARSER_VERSION, convert
from app.ingestion.docling_blocks import to_blocks
from app.ingestion.documents import parsed_document
from app.ingestion.pdf_code import restore_code_lines
from app.ingestion.pdf_exponents import mark_exponents
from app.ingestion.pdf_figures import join_caption_lines, link_figure_labels, mark_figures
from app.ingestion.pdf_furniture import remove_chapter_tabs, remove_contents_and_index
from app.ingestion.pdf_headings import split_long_headings
from app.ingestion.pdf_order import order_by_position
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
    with timer("chapter_tabs"):
        remove_chapter_tabs(conversion.document, path)
    with timer("contents"):
        remove_contents_and_index(conversion.document)
    with timer("figure_labels"):
        link_figure_labels(conversion.document)
    with timer("captions"):
        join_caption_lines(conversion.document)
    with timer("headings"):
        split_long_headings(conversion.document, path)
    with timer("blocks"):
        blocks = to_blocks(conversion.document, "pdf", title)
    with timer("code_lines"):
        blocks = restore_code_lines(blocks, conversion.document, path)
    with timer("exponents"):
        blocks = mark_exponents(blocks, path)
    with timer("order"):
        blocks = order_by_position(blocks, conversion.document)
    with timer("figures"):
        blocks = mark_figures(blocks, conversion.document)
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
