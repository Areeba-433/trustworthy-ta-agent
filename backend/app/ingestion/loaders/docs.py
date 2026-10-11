"""Digital PDF, DOCX and PPTX through Docling. Owner: Areeba.

load() turns one file into a ParsedDocument in four steps:
  1. convert it with Docling (OCR off), or reuse the saved result for this exact file
  2. walk Docling's items in reading order, keeping track of the headings above each one
  3. clean the text (never tables or code) and detect its language
  4. drop headers and footers Docling missed, number the blocks, report the quality
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from collections import defaultdict
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from app.ingestion import messages
from app.ingestion.cleaning.common import (clean_text, detect_lang, find_repeated_lines, garbage_share,
                                           is_repeated, title_from_filename)
from app.ingestion.contract import Block, Location, ParsedDocument, QualityReport, ResourceMeta
from app.ingestion.dispatcher import failed_document
from app.ingestion.loaders import fast_pdf
from app.ingestion.precheck import GARBAGE_MAX
from app.ingestion.registry import register
from app.ingestion.storage import Timer, cache_path, raw_dir

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

logger = logging.getLogger("tta.ingestion.docs")

PARSER = "docling"
CACHE_VARIANT = "no-ocr-headings-fast-tables"     # change this whenever the conversion options change, so old saved results aren't reused

# Docling's label for an item -> the block kind in our contract. Labels not listed (pictures,
# page headers and footers, form fields) carry no text we keep.
KIND_BY_LABEL = {
    "title": "heading",
    "section_header": "heading",
    "text": "paragraph",
    "paragraph": "paragraph",
    "footnote": "paragraph",
    "formula": "paragraph",
    "list_item": "list_item",
    "caption": "caption",
    "table": "table",
    "document_index": "table",          # a book's contents pages: Docling reads them as a table
    "code": "code",
    "checkbox_selected": "paragraph",   # Docling sometimes takes a drawing of boxes (an array, a stack) for a
    "checkbox_unselected": "paragraph", # form: the words in it are still the book's words
    "handwritten_text": "paragraph",
    "reference": "paragraph",
}
NOT_CLEANED = {"table", "code", "formula"}      # cleaning could change their meaning
REPEATS_CHECKED = {"paragraph", "caption"}       # where headers and footers Docling missed end up


def docling_version() -> str:
    return version("docling")


def cache_variant(source_type: str) -> str:
    """The name saved results go under: it changes with the conversion options and the fast path's version."""
    fast = source_type == "pdf" and fast_pdf_on()
    return CACHE_VARIANT + (f"-fast-pdf-{fast_pdf.VERSION}" if fast else "")


def fast_pdf_on() -> bool:
    """The fast path for long PDFs (fast_pdf.py). Set INGESTION_FAST_PDF=0 to send every page to Docling."""
    return os.getenv("INGESTION_FAST_PDF", "1") != "0"


@lru_cache(maxsize=1)
def _converter():
    """Docling's converter, built once: setting it up loads its models, so every file reuses it."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode, TableStructureOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_options = PdfPipelineOptions(
        do_ocr=False,                       # scans go to the OCR loader
        do_table_structure=True,
        table_structure_options=TableStructureOptions(mode=TableFormerMode.FAST),   # 1.2x faster, same tables in our test
    )
    pdf_options.heading_hierarchy_options.enabled = True    # otherwise every PDF heading comes back as level 1
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)},
    )


def convert(path: Path, meta: ResourceMeta) -> tuple[DoclingDocument | None, bool]:
    """(Docling's document, whether it read the whole file). None if it couldn't read the file at all.

    A complete result is saved under the file's hash, so the same file is never converted twice.
    """
    from docling.datamodel.base_models import ConversionStatus
    from docling_core.types.doc import DoclingDocument, ImageRefMode

    fast = meta.precheck.source_type == "pdf" and fast_pdf_on()
    variant = cache_variant(meta.precheck.source_type)
    saved = cache_path(meta.file_sha256, PARSER, docling_version(), variant)
    if saved.exists():
        document, complete = DoclingDocument.load_from_json(saved), True
    else:
        document = None
        if fast:                            # long digital PDFs: plain pages read directly, Docling for the rest
            def batch_file(key: str) -> Path:
                return cache_path(meta.file_sha256, PARSER, docling_version(), f"{variant}-part-{key}")

            try:
                document, complete, report = fast_pdf.convert_pdf(
                    path, _converter, batch_file, workers=fast_pdf.docling_workers(),
                    converter_name=f"{__name__}:_converter")
                logger.info("%s: %s", meta.file_name, report)
            except Exception:                 # the fast path must never cost a file: Docling reads it whole
                logger.exception("fast path failed on %s; Docling reads the whole file", meta.file_name)
                document = None
        if document is None:
            result = _converter().convert(path, raises_on_error=False)
            if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
                logger.warning("docling could not read %s: %s", meta.file_name, result.errors)
                return None, False
            document, complete = result.document, result.status == ConversionStatus.SUCCESS
        if complete:
            tmp = saved.with_name(f"{saved.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
            document.save_as_json(tmp, image_mode=ImageRefMode.PLACEHOLDER)
            tmp.replace(saved)          # all or nothing: a crash never leaves half a file in the cache
    if saved.exists():
        shutil.copyfile(saved, raw_dir(meta.resource_id) / "docling.json")   # the raw output, kept per upload
    return document, complete


# "Lecture 05: Arrays", "Chapter 3", "Week 2": a top-level part of a course file, whatever its font size
_PART = re.compile(r"^\s*(lecture|chapter|unit|week|module|part)\s*(no\.?|#)?\s*[-:.]?\s*\d+\b", re.IGNORECASE)
# a label over the content that follows ("Example 3:", "Sample output", "Task # 2"), not the start of a section
_LABEL = re.compile(r"^\s*(examples?|sample\s*output|program\s*output|output|ouput|note|task|homework|demo|"
                    r"exercises?|solution|hint)\s*(#\s*)?(\d+\b|:\s*$)", re.IGNORECASE)   # a number, or ":" alone


def _heading_like(text: str, source_type: str) -> bool:
    """Is this short text a heading, or a line a PDF reader took for one (a label, a code line, a sentence)?"""
    if _PART.match(text) or source_type != "pdf":
        return True
    words = text.split()
    text = text.strip()
    ends = text.endswith((".", ",", ":", ";", "\u201d", '"'))      # a question ("6.8 What is the output ...?") stays
    sentence = (len(words) > 14 or (len(words) > 10 and "," in text) or (len(words) > 7 and ends)
                or (len(words) > 3 and text[:1].islower()       # the end of a sentence ("will generate the function"),
                    and (ends or text.endswith("?") or not any(w[:1].isupper() for w in words[1:]))))
                                                                # not "string Member Functions and Operators"
    # a line of code; "2.8 The C++ string Class", "Mixing cin >> and cin.get" are headings of a C++ book
    code = (re.search(r"[;{}]", text) or text.startswith(("//", "#include", "/*")) or re.fullmatch(r"\w+\(\)", text)
            or (text[:1].islower() and re.search(r"==|<<|>>|\w\+\+|\w\(\)|\w\[\d*\]|\s=\s", text)))
    return not (sentence or code or _LABEL.match(text) or text.startswith("o ") or "\u2022" in text)


def _parts(document: DoclingDocument) -> set[str]:
    """The "Lecture N" headings that divide a set of lectures, each starting its own page. A page listing
    several ("Chapter 1 ... Chapter 2 ..." in a book's contents) is a list, not where parts start, and so is
    the last page of that list, with one left over. Fewer than two: the file is one lecture, and its
    "Lecture 5: Joins" stays its title."""
    by_page: dict[int, list] = defaultdict(list)
    for item, _ in document.iterate_items():
        if item.label.value in ("title", "section_header") and _PART.match(item.text) and item.prov:
            by_page[item.prov[0].page_no].append(item)
    listing = {page for page, items in by_page.items() if len(items) > 1}
    found = {items[0].self_ref for page, items in by_page.items()
             if len(items) == 1 and not {page - 1, page + 1} & listing}
    return found if len(found) >= 2 else set()


def document_title(document: DoclingDocument, source_type: str, file_name: str) -> str:
    """The first title Docling found (PDF, DOCX), else the file name. A deck's title is its file name.
    In a set of lectures, "Lecture 01: Recap" is the first lecture's heading, not the file's title."""
    if source_type != "pptx":
        parts = _parts(document)
        for item, _ in document.iterate_items():
            if item.label.value == "title" and clean_text(item.text) and item.self_ref not in parts:
                return clean_text(item.text)
    return title_from_filename(file_name)


def _heading_levels(document: DoclingDocument, source_type: str) -> dict[int, int]:
    """Docling's heading levels (or the fast reader's) squeezed into 1 to 4: parts ("Lecture 05") are 1, the
    other levels follow in their order below them, so a run of bold lines cannot nest a dozen deep."""
    from docling_core.types.doc import ContentLayer

    found = set()
    parts = _parts(document)
    for item, _ in document.iterate_items(included_content_layers={ContentLayer.BODY}):
        if _kind(item, document) == "heading" and item.label.value != "title":
            text = clean_text(item.text)
            if text and item.self_ref not in parts and _heading_like(text, source_type):
                found.add(getattr(item, "level", 1))
    first = 2 if parts else 1
    return {level: min(first + rank, 4) for rank, level in enumerate(sorted(found))}


def _kind(item, document: DoclingDocument) -> str | None:
    from docling_core.types.doc import ContentLayer, GroupLabel

    if item.content_layer == ContentLayer.FURNITURE:      # Word keeps footnotes here, beside page headers and footers
        return "paragraph" if item.label.value == "footnote" else None
    if item.content_layer == ContentLayer.NOTES:          # PowerPoint: speaker notes, and reviewers' comments
        parent = item.parent.resolve(document) if item.parent else None
        if getattr(parent, "label", None) == GroupLabel.COMMENT_SECTION:
            return None
        return "slide_notes" if item.label.value == "text" else None
    return KIND_BY_LABEL.get(item.label.value)


def _inside(item, document: DoclingDocument, kind) -> bool:
    parent = item.parent.resolve(document) if item.parent else None
    while parent is not None:
        if isinstance(parent, kind):
            return True
        parent = parent.parent.resolve(document) if parent.parent else None
    return False


def _inside_table(item, document: DoclingDocument) -> bool:
    """Word lists the text of formatted table cells again as separate items; the table block already has it.
    A table's caption and its notes hang under the table too, but they are not in its cells: they stay."""
    from docling_core.types.doc import TableItem

    return item.label.value not in ("caption", "footnote") and _inside(item, document, TableItem)


def _table_markdown(item) -> str:
    """A table as Markdown, with a cell that spans several rows or columns written once, in its first
    position (Docling's own writer repeats it in every column it covers: "ASCII | ASCII | ASCII")."""
    data = getattr(item, "data", None)
    if data is None or not data.num_rows or not data.num_cols:
        return ""
    if not any(cell.end_row_offset_idx - cell.start_row_offset_idx > 1 or
               cell.end_col_offset_idx - cell.start_col_offset_idx > 1 for cell in data.table_cells):
        return ""                                 # no cell spans others: Docling's own writer is right
    grid = [["" for _ in range(data.num_cols)] for _ in range(data.num_rows)]
    for cell in data.table_cells:
        r, c = cell.start_row_offset_idx, cell.start_col_offset_idx
        if 0 <= r < data.num_rows and 0 <= c < data.num_cols:
            grid[r][c] = " ".join(cell.text.split()).replace("|", "\\|")
    if not any(any(row) for row in grid):
        return ""
    lines = ["| " + " | ".join(grid[0]) + " |", "| " + " | ".join("---" for _ in grid[0]) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in grid[1:]]
    return "\n".join(lines)


def walk(document: DoclingDocument, source_type: str, title: str) -> list[dict]:
    """Docling's items in reading order -> raw blocks (text not cleaned yet), each with its heading path."""
    from docling_core.types.doc import ContentLayer, PictureItem

    raw: list[dict] = []
    headings: list[tuple[int, str]] = []    # the headings above the current item: (level, text)
    unit = 1                                # current page (PDF) or slide (PPTX)
    slide_title: str | None = None
    title_seen = False
    tables = None                           # Markdown writer for tables, made once (see below)
    levels = _heading_levels(document, source_type)
    parts = _parts(document)
    # traverse_pictures: the words inside a diagram (labels, boxes, a UML class) are text of the book too
    for item, _ in document.iterate_items(included_content_layers={ContentLayer.BODY, ContentLayer.NOTES, ContentLayer.FURNITURE},
                                          traverse_pictures=True):
        page = item.prov[0].page_no if getattr(item, "prov", None) else unit
        if source_type == "pptx" and page != unit:
            headings, slide_title = [], None        # a new slide starts with no headings
        unit = page
        kind = _kind(item, document)
        if kind is None or (kind != "table" and _inside_table(item, document)):
            continue
        in_picture = kind != "caption" and _inside(item, document, PictureItem)
        if in_picture and kind == "heading":
            kind = "paragraph"                  # a label in a diagram never starts a section
        if kind == "heading" and not _heading_like(clean_text(item.text), source_type):
            kind = "paragraph"                  # "Example 3:", a code line, a whole sentence in bold
        if kind == "table":
            if tables is None:
                # item.export_to_markdown(doc=...) builds this writer again for every table, and building it
                # checks the whole document: a 1,200-page book with 400 tables took almost 2 minutes that way.
                from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
                tables = MarkdownDocSerializer(doc=document)
            text = _table_markdown(item) or tables.serialize(item=item).text
        else:
            text = item.text
        if not text.strip():
            continue
        if kind == "heading":
            name = clean_text(text)
            if not name:
                continue
            if source_type == "pptx" and item.label.value == "title":
                slide_title, headings = name, []
            elif item.label.value == "title" and not title_seen and item.self_ref not in parts:
                title_seen = True                  # the document's own title is already heading_path[0]
            else:
                level = 1 if item.self_ref in parts else levels.get(getattr(item, "level", 1), 4)
                headings = [h for h in headings if h[0] < level] + [(level, name)]
        context = [slide_title or f"Slide {unit}"] if source_type == "pptx" else []
        extra = {"ref": item.self_ref}
        if in_picture:
            extra["in_picture"] = True      # a label inside a figure, not running text
        pages = sorted({p.page_no for p in item.prov}) if getattr(item, "prov", None) else []
        if len(pages) > 1:
            extra["pages"] = pages          # a paragraph that runs onto the next page: Docling joins the two halves
        if kind == "list_item" and getattr(item, "marker", ""):
            extra["marker"] = item.marker
        raw.append({"kind": kind, "label": item.label.value, "text": text, "unit": unit,
                    "path": [title, *context, *(h[1] for h in headings)], "extra": extra})
    return raw


def to_blocks(raw: list[dict], source_type: str) -> list[Block]:
    """Clean, drop repeated headers and footers, add the location, number the blocks 0, 1, 2 ..."""
    repeated: set[str] = set()
    if source_type in ("pdf", "pptx"):
        lines_by_unit: dict[int, list[str]] = defaultdict(list)
        for r in raw:
            if r["kind"] in REPEATS_CHECKED and not r["extra"].get("in_picture"):
                lines_by_unit[r["unit"]].append(r["text"])
        repeated = find_repeated_lines(lines_by_unit)
    blocks: list[Block] = []
    for r in raw:                           # a figure's labels ("null", "Pointer") may repeat: they stay
        if r["kind"] in REPEATS_CHECKED and not r["extra"].get("in_picture") and is_repeated(r["text"], repeated):
            continue
        text = r["text"] if r["kind"] in NOT_CLEANED or r["label"] in NOT_CLEANED else clean_text(r["text"])
        if not text.strip():
            continue
        loc = (Location(page=r["unit"]) if source_type == "pdf"
               else Location(slide=r["unit"]) if source_type == "pptx" else Location())
        blocks.append(Block(seq=len(blocks), kind=r["kind"], text=text, heading_path=r["path"], loc=loc,
                            lang="code" if r["kind"] == "code" else detect_lang(text), extra=r["extra"]))
    return blocks


@register("pdf", "docx", "pptx")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    source_type = meta.precheck.source_type
    timer = Timer()
    try:
        with timer("docling"):
            document, complete = convert(path, meta)
    except Exception:                      # a bad file must never crash the loader
        logger.exception("docling crashed on %s", meta.file_name)
        document, complete = None, False
    if document is None:
        return failed_document(meta, source_type, messages.UNREADABLE)

    with timer("blocks"):
        title = document_title(document, source_type, meta.file_name)
        blocks = to_blocks(walk(document, source_type, title), source_type)
    if not blocks:
        return failed_document(meta, source_type, messages.NO_TEXT_FILE)

    status, warnings = "ok", []
    if not complete:
        status = "degraded"
        warnings.append(messages.PARTIAL)
    all_text = "\n".join(b.text for b in blocks)
    if garbage_share(all_text) > GARBAGE_MAX:
        status = "degraded"
        warnings.append(messages.GARBLED)
    units = sorted(document.pages) if source_type != "docx" else [1]     # DOCX has no pages
    if source_type != "docx":
        covered = {b.loc.page or b.loc.slide for b in blocks}
        covered |= {page for b in blocks for page in b.extra.get("pages", [])}
        empty = sorted(set(units) - covered)
        if empty:
            warnings.append(messages.no_text_units("Pages" if source_type == "pdf" else "Slides", empty))
    if meta.precheck.large_image_pages:
        logger.info("%s: pictures on pages %s may hold text that isn't read yet (OCR is off)",
                    meta.file_name, meta.precheck.large_image_pages)

    return ParsedDocument(
        resource_id=meta.resource_id, course_id=meta.course_id, file_name=meta.file_name,
        file_sha256=meta.file_sha256, source_type=source_type, title=title,
        parser=PARSER, parser_version=docling_version(), blocks=blocks,
        quality=QualityReport(status=status, warnings=warnings, units_total=len(units),
                              chars_total=sum(len(b.text) for b in blocks), seconds_taken=timer.seconds),
    )