"""Digital PDF, DOCX and PPTX through Docling. Owner: Areeba.

load() turns one file into a ParsedDocument in four steps:
  1. convert it with Docling (OCR off), or reuse the saved result for this exact file
  2. walk Docling's items in reading order, keeping track of the headings above each one
  3. clean the text (never tables or code) and detect its language
  4. drop headers and footers Docling missed, number the blocks, report the quality
"""
from __future__ import annotations

import logging
import shutil
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
from app.ingestion.precheck import GARBAGE_MAX
from app.ingestion.registry import register
from app.ingestion.storage import Timer, cache_path, raw_dir

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

logger = logging.getLogger("tta.ingestion.docs")

PARSER = "docling"
CACHE_VARIANT = "no-ocr"     # change this whenever the conversion options change, so old saved results aren't reused

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
    "code": "code",
}
NOT_CLEANED = {"table", "code", "formula"}      # cleaning could change their meaning
REPEATS_CHECKED = {"paragraph", "caption"}       # where headers and footers Docling missed end up


def docling_version() -> str:
    return version("docling")


@lru_cache(maxsize=1)
def _converter():
    """Docling's converter, built once: setting it up loads its models, so every file reuses it."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)   # scans go to the OCR loader
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

    saved = cache_path(meta.file_sha256, PARSER, docling_version(), CACHE_VARIANT)
    if saved.exists():
        document, complete = DoclingDocument.load_from_json(saved), True
    else:
        result = _converter().convert(path, raises_on_error=False)
        if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            logger.warning("docling could not read %s: %s", meta.file_name, result.errors)
            return None, False
        document, complete = result.document, result.status == ConversionStatus.SUCCESS
        if complete:
            tmp = saved.with_suffix(".json.tmp")
            document.save_as_json(tmp, image_mode=ImageRefMode.PLACEHOLDER)
            tmp.replace(saved)          # all or nothing: a crash never leaves half a file in the cache
    if saved.exists():
        shutil.copyfile(saved, raw_dir(meta.resource_id) / "docling.json")   # the raw output, kept per upload
    return document, complete


def document_title(document: DoclingDocument, source_type: str, file_name: str) -> str:
    """The first title Docling found (PDF, DOCX), else the file name. A deck's title is its file name."""
    if source_type != "pptx":
        for item, _ in document.iterate_items():
            if item.label.value == "title" and clean_text(item.text):
                return clean_text(item.text)
    return title_from_filename(file_name)


def _kind(item, document: DoclingDocument) -> str | None:
    from docling_core.types.doc import ContentLayer, GroupLabel

    if item.content_layer == ContentLayer.NOTES:          # PowerPoint: speaker notes, and reviewers' comments
        parent = item.parent.resolve(document) if item.parent else None
        if getattr(parent, "label", None) == GroupLabel.COMMENT_SECTION:
            return None
        return "slide_notes" if item.label.value == "text" else None
    return KIND_BY_LABEL.get(item.label.value)


def walk(document: DoclingDocument, source_type: str, title: str) -> list[dict]:
    """Docling's items in reading order -> raw blocks (text not cleaned yet), each with its heading path."""
    from docling_core.types.doc import ContentLayer

    raw: list[dict] = []
    headings: list[tuple[int, str]] = []    # the headings above the current item: (level, text)
    unit = 1                                # current page (PDF) or slide (PPTX)
    slide_title: str | None = None
    title_seen = False
    for item, _ in document.iterate_items(included_content_layers={ContentLayer.BODY, ContentLayer.NOTES}):
        page = item.prov[0].page_no if getattr(item, "prov", None) else unit
        if source_type == "pptx" and page != unit:
            headings, slide_title = [], None        # a new slide starts with no headings
        unit = page
        kind = _kind(item, document)
        if kind is None:
            continue
        text = item.export_to_markdown(doc=document) if kind == "table" else item.text
        if not text.strip():
            continue
        if kind == "heading":
            name = clean_text(text)
            if not name:
                continue
            if source_type == "pptx" and item.label.value == "title":
                slide_title, headings = name, []
            elif item.label.value == "title" and not title_seen:
                title_seen = True                  # the document's own title is already heading_path[0]
            else:
                level = getattr(item, "level", 1)
                headings = [h for h in headings if h[0] < level] + [(level, name)]
        context = [slide_title or f"Slide {unit}"] if source_type == "pptx" else []
        extra = {"ref": item.self_ref}
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
            if r["kind"] in REPEATS_CHECKED:
                lines_by_unit[r["unit"]].append(r["text"])
        repeated = find_repeated_lines(lines_by_unit)
    blocks: list[Block] = []
    for r in raw:
        if r["kind"] in REPEATS_CHECKED and is_repeated(r["text"], repeated):
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
        empty = sorted(set(units) - {b.loc.page or b.loc.slide for b in blocks})
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