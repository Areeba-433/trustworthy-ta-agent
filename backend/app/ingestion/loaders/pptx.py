"""PowerPoint loader: Docling's PowerPoint reader, then the shared to_blocks(), then the slide rules.

Each rule answers something measured on Docling 2.134.0 (step 1 of the PPTX plan, then Phase 0 and Phase 1):
- a footer typed on each slide comes out as a plain paragraph, so a paragraph repeated on most slides is dropped;
- to_blocks() lets a heading run on into later slides, so each slide keeps only its own headings;
- a slide whose only text is its title, with a picture that is not an icon, is named for the teacher, and a deck
  whose only text is titles is refused: headings add no text, so the chunker would make no chunk (Phase 0);
- Docling keeps a chart's numbers on the chart's picture, which to_blocks() leaves out: each becomes a table block.
Slide numbers, speaker notes and reviewers' comments need no rule here: to_blocks() already handles them.
Broken files need none either: convert() raises FileRefused and ingest_file() turns it into a failed document.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.ingestion import messages
from app.ingestion.cleaning.common import detect_lang, find_repeated_lines, is_repeated, title_from_filename
from app.ingestion.contract import Block, BlockKind, Location, ParsedDocument, ResourceMeta, SourceType
from app.ingestion.documents import FileRefused, parsed_document
from app.ingestion.registry import register

if TYPE_CHECKING:                       # type hints only: importing docling-core takes seconds
    from docling_core.types.doc import DoclingDocument

SOURCE_TYPE: SourceType = "pptx"
FOOTER_KIND: BlockKind = "paragraph"    # footers reach us as plain paragraphs; headings and notes are never footers
SLIDES = "Slides"                       # the unit name messages.no_text_units() expects (plural)
ICON_SIDE_PX = 64                       # figures plan: a picture with a side under 64 px is an icon, not content


@register("pptx", heavy=True)
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    from app.ingestion import converter                  # 9 s to import (step 1): only once a deck is really loaded

    found = extract(path, meta.file_sha256, title_from_filename(meta.file_name))
    if found.blocks and all(b.kind == "heading" for b in found.blocks):
        raise FileRefused(messages.NO_TEXT_FILE)         # headings add no text: the chunker would make no chunk
    return parsed_document(
        meta, title=found.title, blocks=found.blocks,
        parser=converter.PARSER, parser_version=converter.PARSER_VERSION,
        units_total=len(found.document.pages),           # every slide, empty and hidden ones included
        problems=found.problems,
    )


@dataclass(frozen=True)
class Extraction:
    """What load() decides from, before any refusal. Tests and scripts read it too."""

    title: str
    document: "DoclingDocument"
    blocks: list[Block]
    problems: list[str]


def extract(path: Path, file_sha256: str | None, title: str) -> Extraction:
    from app.ingestion import converter
    from app.ingestion.docling_blocks import to_blocks   # 2 s to import (step 1)

    conversion = converter.convert(path, SOURCE_TYPE, file_sha256)          # a broken file raises FileRefused
    blocks = _own_slide_headings(_drop_footers(to_blocks(conversion.document, SOURCE_TYPE, title)))
    blocks = _insert(blocks, _chart_tables(conversion.document, blocks, title))
    problems = [*conversion.problems, *_picture_only_slides(conversion.document, blocks)]
    return Extraction(title, conversion.document, blocks, problems)


def _drop_footers(blocks: list[Block]) -> list[Block]:
    """Drop paragraphs repeated on most slides, such as "CS-201 Data Structures" typed in every footer.

    "Most" is the shared rule for running headers and footers, find_repeated_lines(): on more than half the slides
    that have any text, and only in decks with at least three such slides.
    """
    paragraphs: dict[int, list[str]] = {_slide(b): [] for b in blocks}
    for b in blocks:
        if b.kind == FOOTER_KIND:
            paragraphs[_slide(b)].append(b.text)
    footers = find_repeated_lines(paragraphs)
    return [b for b in blocks if b.kind != FOOTER_KIND or not is_repeated(b.text, footers)]


def _own_slide_headings(blocks: list[Block]) -> list[Block]:
    """Each block's heading_path keeps only the headings of its own slide.

    to_blocks() lets a heading run on until the next one, which suits a book. On slides it gave a slide without a
    title (and a slide titled with the deck's own name, which to_blocks() leaves out) the previous slide's title,
    so the citation named the wrong topic.
    """
    own: dict[int, set[str]] = {}
    for b in blocks:
        if b.kind == "heading":
            own.setdefault(_slide(b), set()).add(b.text)
    fixed: list[Block] = []
    for b in blocks:
        headings = own.get(_slide(b), set())
        path = [b.heading_path[0]] + [h for h in b.heading_path[1:] if h in headings]
        fixed.append(b if path == b.heading_path else _with_heading_path(b, path))
    return fixed


def _with_heading_path(block: Block, heading_path: list[str]) -> Block:
    """A new, validated Block: Pydantic checks an object only when it is created, so one is never edited."""
    return Block.model_validate({**block.model_dump(), "heading_path": heading_path})


def _chart_tables(doc: "DoclingDocument", blocks: list[Block], title: str) -> list[Block]:
    """One table block per chart, from the grid Docling keeps on the chart's picture (meta.tabular_chart)."""
    from docling_core.types.doc import DocItemLabel, TableItem

    found = []
    for picture in doc.pictures:
        chart = picture.meta.tabular_chart if picture.meta is not None else None
        if chart is None or chart.chart_data is None or not picture.prov:
            continue
        table = TableItem(self_ref="#/tables/0", label=DocItemLabel.TABLE, data=chart.chart_data)
        text = table.export_to_markdown(doc=doc).strip()    # the same Markdown to_blocks() writes for a table
        if text:
            found.append(_new_block("table", text, picture.prov[0].page_no, blocks, title, ref=picture.self_ref))
    return found


def _new_block(kind: BlockKind, text: str, slide: int, blocks: list[Block], title: str, **extra: object) -> Block:
    """A block for content to_blocks() never saw, under the heading path of its slide's content (seq set later)."""
    on_slide = [b for b in blocks if _slide(b) == slide]
    content = [b for b in on_slide if b.kind != "slide_notes"] or on_slide
    path = content[-1].heading_path if content else [title]
    return Block(seq=0, kind=kind, text=text, heading_path=path, loc=Location(slide=slide), lang=detect_lang(text),
                 extra=extra)


def _insert(blocks: list[Block], additions: list[Block]) -> list[Block]:
    """Each new block goes at the end of its slide's content, before that slide's speaker notes.

    seq is left as it is: parsed_document() numbers every block again, 0, 1, 2 ..., in this order.
    """
    out = list(blocks)
    for new in additions:
        slide = _slide(new)
        notes = [i for i, b in enumerate(out) if _slide(b) == slide and b.kind == "slide_notes"]
        out.insert(notes[0] if notes else sum(1 for b in out if _slide(b) <= slide), new)
    return out


def _picture_only_slides(doc: "DoclingDocument", blocks: list[Block]) -> list[str]:
    """Name for the teacher each slide with a picture or a chart whose only text, if any, is its title.

    A title is a heading, and headings add no text to a chunk, so such a slide answers nothing. Icons don't count:
    a title and a small logo is a section slide, not a missing figure.
    """
    with_text = {_slide(b) for b in blocks if b.kind != "heading"}
    with_picture = {prov.page_no for picture in doc.pictures if not _icon(picture) for prov in picture.prov}
    silent = sorted(with_picture - with_text)
    return [messages.no_text_units(SLIDES, silent)] if silent else []


def _icon(picture) -> bool:
    """Docling stores each picture's size in pixels; a chart, or a picture it could not store, has none."""
    size = picture.image.size if picture.image is not None else None
    return size is not None and min(size.width, size.height) < ICON_SIDE_PX


def _slide(block: Block) -> int:
    """The block's slide number. to_blocks() always sets it for pptx, so a missing one is a bug, not a bad file."""
    if block.loc.slide is None:
        raise ValueError(f"block {block.seq} has no slide number")
    return block.loc.slide