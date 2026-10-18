"""to_blocks(): a DoclingDocument in reading order, as contract Blocks.

Shared by the PDF, DOCX and PPTX loaders. Docling reads the file; this module turns Docling's labels into our
block kinds, gives every block its heading path and location, and leaves out what is not course content
(running headers and footers, contents pages, reviewers' comments). Each loader then applies its own
format-specific fixes to the blocks it gets back.
"""
from collections.abc import Iterator

from docling_core.types.doc import (ContentLayer, DocItem, DocItemLabel, DoclingDocument, GroupItem, GroupLabel,
                                    ListItem, NodeItem, PictureItem, SectionHeaderItem, TableItem)

from app.ingestion.cleaning.common import clean_text, detect_lang
from app.ingestion.contract import Block, BlockKind, Location, SourceType

# Docling label -> our block kind. Every other label is left out on purpose: page_header and page_footer,
# document_index (a contents page), picture (its words come through as figure_text), form fields, checkboxes.
_KIND_BY_LABEL: dict[DocItemLabel, BlockKind] = {
    DocItemLabel.TITLE: "heading",
    DocItemLabel.SECTION_HEADER: "heading",
    DocItemLabel.TEXT: "paragraph",
    DocItemLabel.PARAGRAPH: "paragraph",
    DocItemLabel.FOOTNOTE: "paragraph",
    DocItemLabel.REFERENCE: "paragraph",
    DocItemLabel.LIST_ITEM: "list_item",
    DocItemLabel.CAPTION: "caption",
    DocItemLabel.TABLE: "table",
    DocItemLabel.CODE: "code",
    DocItemLabel.FORMULA: "formula",
}
_VERBATIM: set[BlockKind] = {"table", "code", "formula"}    # never cleaned: spacing and line breaks carry meaning
_LAYERS = {ContentLayer.BODY, ContentLayer.NOTES}           # FURNITURE (headers, footers, page numbers) stays out
_FORMATS: set[SourceType] = {"pdf", "docx", "pptx"}


def to_blocks(doc: DoclingDocument, source_type: SourceType, title: str) -> list[Block]:
    """Blocks numbered 0, 1, 2 ... in reading order; every heading_path starts with `title`."""
    if source_type not in _FORMATS:
        raise ValueError(f"to_blocks() reads Docling formats only, not {source_type!r}")
    blocks: list[Block] = []
    headings: list[tuple[int, str]] = []         # (depth, text) of the headings above the current item
    previous = Location()
    for item, _ in doc.iterate_items(traverse_pictures=True, included_content_layers=_LAYERS):
        if not isinstance(item, DocItem) or item.label not in _KIND_BY_LABEL:
            continue
        ancestors = list(_ancestors(item, doc))
        if any(isinstance(a, GroupItem) and a.label == GroupLabel.COMMENT_SECTION for a in ancestors):
            continue                                              # a reviewer's comment, not course content
        kind = _kind(item, ancestors)
        text = _text(item, kind, doc)
        if not text:
            continue
        loc = previous = _location(item, source_type, previous)
        if kind == "heading":
            depth = item.level if isinstance(item, SectionHeaderItem) else 0     # a title sits above every level
            if depth == 0 and _same_words(text, title):
                continue                                          # already heading_path[0]: don't repeat it
            headings = [h for h in headings if h[0] < depth] + [(depth, text)]
        blocks.append(Block(
            seq=len(blocks), kind=kind, text=text, heading_path=[title] + [h[1] for h in headings], loc=loc,
            lang="code" if kind == "code" else detect_lang(text),
            extra={"ref": item.self_ref},                         # Docling's id: traces a block back to its item
        ))
    return blocks


def _ancestors(item: NodeItem, doc: DoclingDocument) -> Iterator[NodeItem]:
    node = item
    while node.parent is not None:
        node = node.parent.resolve(doc)
        yield node


def _kind(item: DocItem, ancestors: list[NodeItem]) -> BlockKind:
    if item.content_layer == ContentLayer.NOTES:
        return "slide_notes"                                      # PowerPoint speaker notes
    kind = _KIND_BY_LABEL[item.label]
    if kind in ("paragraph", "list_item", "heading") and any(isinstance(a, PictureItem) for a in ancestors):
        return "figure_text"                                      # words inside a figure, e.g. diagram labels
    return kind


def _text(item: DocItem, kind: BlockKind, doc: DoclingDocument) -> str:
    if isinstance(item, TableItem):
        return item.export_to_markdown(doc=doc).strip()
    raw: str = getattr(item, "text", "") or ""
    if kind in _VERBATIM:
        return raw.strip("\n") if raw.strip() else ""             # keep indentation and line breaks
    text = clean_text(raw)
    if text and kind == "list_item" and isinstance(item, ListItem):
        marker = item.marker if item.enumerated and item.marker else "-"
        text = f"{marker} {text}"
    return text


def _location(item: DocItem, source_type: SourceType, previous: Location) -> Location:
    pages = sorted({p.page_no for p in item.prov})
    if source_type == "pdf":
        if not pages:                         # Docling gave no position: it sits where the reading order put it
            return Location(page=previous.page_end or previous.page or 1)
        return Location(page=pages[0], page_end=pages[-1] if pages[-1] > pages[0] else None)
    if source_type == "pptx":
        return Location(slide=pages[0] if pages else previous.slide or 1)
    return Location()                         # DOCX has no pages: its citation is the heading path


def _same_words(a: str, b: str) -> bool:
    return a.casefold().split() == b.casefold().split()