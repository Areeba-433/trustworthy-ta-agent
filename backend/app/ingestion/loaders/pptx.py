"""PowerPoint loader: Docling's PowerPoint reader, then the shared to_blocks(), then the slide rules.

Each rule answers something measured on Docling 2.134.0 (step 1 of the PPTX plan, then Phase 0 and Phase 1):
- a footer typed on each slide comes out as a plain paragraph, so a paragraph repeated on most slides is dropped;
- to_blocks() lets a heading run on into later slides, so each slide keeps only its own headings;
- a slide whose title is a plain text box (no title placeholder; 62 of 81 slides in three real decks) gets that
  text box as its heading, so its chunks cite the slide's topic and not only the deck;
- each slide's title comes first among its blocks: the chunker starts a section at every heading, so text that
  Docling put before the title became a chunk of its own (38 of 39 slides in one real deck);
- to_blocks() gives a picture without words a "[Figure]" block unless it is icon-sized, measured in points, but
  Docling gives PowerPoint positions in EMU, so no slide picture ever counted as an icon: the rule is applied here;
- Docling keeps a chart's numbers on the chart's picture, which to_blocks() leaves out: each becomes a table block
  that carries the chart's figure_id;
- a slide whose only text is its title, with a picture that is not an icon, is named for the teacher: a "[Figure]"
  block holds no words a student could search for. A deck whose only text is titles (no picture either) is
  refused: headings add no text, so the chunker would make no chunk (Phase 0);
- hidden slides are kept, and each of their blocks carries extra["hidden"] = True (contract 2.1 has no field yet).
A coverage audit (_pptx_shapes.audit) puts every shape in "extracted", "skipped:<reason>" or "unknown"; unknown
shapes are logged by slide number and shape type, never by text.
Slide numbers, speaker notes and reviewers' comments need no rule here: to_blocks() already handles them.
Broken files need none either: convert() raises FileRefused and ingest_file() turns it into a failed document.
"""
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.ingestion import messages
from app.ingestion.cleaning.common import detect_lang, find_repeated_lines, is_repeated, title_from_filename
from app.ingestion.contract import Block, BlockKind, Location, ParsedDocument, ResourceMeta, SourceType
from app.ingestion.documents import FileRefused, parsed_document
from app.ingestion.loaders import _pptx_shapes as shapes
from app.ingestion.registry import register

if TYPE_CHECKING:                       # type hints only: importing docling-core takes seconds
    from docling_core.types.doc import DoclingDocument

logger = logging.getLogger("tta.ingestion")

SOURCE_TYPE: SourceType = "pptx"
FOOTER_KIND: BlockKind = "paragraph"    # footers reach us as plain paragraphs; headings and notes are never footers
SLIDES = "Slides"                       # the unit name messages.no_text_units() expects (plural)
ICON_SIDE_PT = 48                       # to_blocks()'s icon rule: under 48 points on both sides is an icon
EMU_PER_POINT = 12700                   # Docling gives PowerPoint positions in EMU, PowerPoint's own unit
TITLE_TOP = 0.5                         # a text-box title starts in the upper half of the slide
TITLE_NEAR_LARGEST = 0.9                # the topmost text this close to the largest wins: a formula may be bigger
TITLE_OVER_BODY = 1.25                  # and it must be clearly larger than the slide's other text (median)
TITLE_MAX_WORDS = 15


@register("pptx", heavy=True)
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    from app.ingestion import converter                  # 9 s to import (step 1): only once a deck is really loaded

    found = extract(path, meta.file_sha256, title_from_filename(meta.file_name))
    if found.blocks and all(b.kind == "heading" for b in found.blocks):
        raise FileRefused(messages.NO_TEXT_FILE)         # titles only: headings add no text, so there'd be no chunk
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
    deck: shapes.Deck
    blocks: list[Block]
    coverage: list[shapes.Entry]
    problems: list[str]


def extract(path: Path, file_sha256: str | None, title: str) -> Extraction:
    from app.ingestion import converter
    from app.ingestion.docling_blocks import to_blocks   # 2 s to import (step 1)

    conversion = converter.convert(path, SOURCE_TYPE, file_sha256)          # a broken file raises FileRefused
    deck = _read_deck(path)                                                 # after convert(): the file is sound
    raw = _drop_icon_figures(to_blocks(conversion.document, SOURCE_TYPE, title), conversion.document)
    kept = _drop_footers(raw)
    blocks = _title_first(_promote_titles(_own_slide_headings(kept), deck))
    blocks = _insert(blocks, _chart_tables(conversion.document, blocks, title))
    blocks = _mark_hidden(blocks, deck.hidden_slides)
    blocks = [b.model_copy(update={"seq": i}) for i, b in enumerate(blocks)]
    kept_seqs = {b.seq for b in kept}
    footers = [b.text for b in raw if b.seq not in kept_seqs]                # what _drop_footers() took out
    coverage = shapes.audit(deck, blocks, footers, title)
    _log_coverage(coverage)
    problems = [*conversion.problems, *_picture_only_slides(conversion.document, blocks)]
    return Extraction(title, conversion.document, deck, blocks, coverage, problems)


def _read_deck(path: Path) -> shapes.Deck:
    """python-pptx's one pass. If it fails where Docling did not, keep Docling's result and log the error type."""
    try:
        return shapes.read_deck(path)
    except Exception as exc:
        logger.warning("pptx shapes pass failed (%s): no hidden flags, audit or extra text", type(exc).__name__)
        return shapes.Deck([])


def _drop_icon_figures(blocks: list[Block], doc: "DoclingDocument") -> list[Block]:
    """Drop the "[Figure]" block of an icon-sized picture, as to_blocks() means to.

    to_blocks() compares a picture's size with 48 in points (PDF) or pixels, but Docling gives PowerPoint positions
    in EMU (12,700 per point), so on a slide no picture was ever that small. _icon() measures it in points.
    """
    return [b for b in blocks if b.kind != "figure" or not _icon(_picture(doc, b.figure_id))]


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


def _promote_titles(blocks: list[Block], deck: shapes.Deck) -> list[Block]:
    """A slide with no heading whose title is a plain text box: that paragraph becomes the slide's heading.

    Every block of the slide is then cited under it, as under a title placeholder. Like any heading, the title
    then adds no text to the chunk. A title with the deck's own name is left alone, as to_blocks() does.
    """
    on_slide: dict[int, list[int]] = {}
    for i, b in enumerate(blocks):
        on_slide.setdefault(_slide(b), []).append(i)
    out = list(blocks)
    for slide in deck.slides:
        here = on_slide.get(slide.number, [])
        if not here or any(out[i].kind == "heading" for i in here):
            continue
        title = _slide_title(slide)
        match = next((i for i in here if out[i].kind == "paragraph" and title is not None
                      and shapes.norm(out[i].text) == shapes.norm(title)), None)
        if match is None or shapes.same_words(out[match].text, out[match].heading_path[0]):
            continue
        path = [out[match].heading_path[0], out[match].text]
        for i in here:
            fields = {"heading_path": path, **({"kind": "heading"} if i == match else {})}
            out[i] = Block.model_validate({**out[i].model_dump(), **fields})
    return out


def _slide_title(slide: shapes.Slide) -> str | None:
    """The text box that looks like the slide's title, or None.

    Among one-paragraph text boxes of up to 15 words starting in the upper half, take the largest font size; the
    topmost box within 90% of it wins (a formula box under the title may be bigger). It counts only if it is at
    least 1.25 times the median size of the slide's other text, so a lone text box, or several of one size, is
    never a title. A placeholder is never a candidate (a title placeholder is a heading already), but its text
    counts as other text, at the size _pptx_shapes can resolve (the deck's default when the layout sets it).
    """
    worded = [s for s in slide.shapes if s.kind == "text" and any(shapes.norm(line) for line in s.lines)]
    candidates = [s for s in worded if s.placeholder is None and len(s.lines) == 1 and s.top is not None
                  and s.top < TITLE_TOP and s.size and len(s.lines[0].split()) <= TITLE_MAX_WORDS]
    if not candidates:
        return None
    largest = max(s.size for s in candidates)
    title = min((s for s in candidates if s.size >= TITLE_NEAR_LARGEST * largest), key=lambda s: s.top)
    others = sorted(s.size for s in worded if s is not title and s.size)
    if not others or title.size < TITLE_OVER_BODY * others[len(others) // 2]:
        return None
    return title.lines[0]


def _title_first(blocks: list[Block]) -> list[Block]:
    """Each slide's first heading moves to the front of that slide's blocks, and what came before it goes under it.

    Docling reads shapes in the order they were added, so a title box added last comes after the slide's other
    text. The chunker starts a section at every heading, so that text became a chunk of its own, apart from the
    rest of the slide. Placeholder titles are usually first already; then nothing moves.
    """
    out: list[Block] = []
    for slide in dict.fromkeys(_slide(b) for b in blocks):
        here = [b for b in blocks if _slide(b) == slide]
        first = next((i for i, b in enumerate(here) if b.kind == "heading"), 0)     # 0: first already, or none
        if first:
            title = here[first]
            here = [title, *(_with_heading_path(b, title.heading_path) for b in here[:first]), *here[first + 1:]]
        out += here
    return out


def _with_heading_path(block: Block, heading_path: list[str]) -> Block:
    """A new, validated Block: Pydantic checks an object only when it is created, so one is never edited."""
    return Block.model_validate({**block.model_dump(), "heading_path": heading_path})


def _chart_tables(doc: "DoclingDocument", blocks: list[Block], title: str) -> list[Block]:
    """One table block per chart, from the grid Docling keeps on the chart's picture (meta.tabular_chart).

    The table carries the chart's figure_id, as the words inside a picture do: its chunk then lists the chart too.
    """
    from docling_core.types.doc import DocItemLabel, TableItem

    from app.ingestion.docling_blocks import figure_name

    found = []
    for picture in doc.pictures:
        chart = picture.meta.tabular_chart if picture.meta is not None else None
        if chart is None or chart.chart_data is None or not picture.prov:
            continue
        table = TableItem(self_ref="#/tables/0", label=DocItemLabel.TABLE, data=chart.chart_data)
        text = table.export_to_markdown(doc=doc).strip()    # the same Markdown to_blocks() writes for a table
        if text:
            found.append(_new_block("table", text, picture.prov[0].page_no, blocks, title,
                                    figure_id=figure_name(picture), ref=picture.self_ref))
    return found


def _new_block(kind: BlockKind, text: str, slide: int, blocks: list[Block], title: str,
               figure_id: str | None = None, **extra: object) -> Block:
    """A block for content to_blocks() never saw, under the heading path of its slide's content (seq set later)."""
    on_slide = [b for b in blocks if _slide(b) == slide]
    content = [b for b in on_slide if b.kind != "slide_notes"] or on_slide
    path = content[-1].heading_path if content else [title]
    return Block(seq=0, kind=kind, text=text, heading_path=path, loc=Location(slide=slide), lang=detect_lang(text),
                 figure_id=figure_id, extra=extra)


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


def _log_coverage(coverage: list[shapes.Entry]) -> None:
    counts = Counter(entry.bucket.split(":")[0] for entry in coverage)
    logger.info("pptx coverage: extracted %d, skipped %d, unknown %d",
                counts["extracted"], counts["skipped"], counts["unknown"])
    for entry in coverage:
        if entry.bucket == "unknown":
            logger.warning("pptx coverage: slide %d, %s not accounted for", entry.slide, entry.tag)


def _mark_hidden(blocks: list[Block], hidden: set[int]) -> list[Block]:
    """Blocks of hidden slides stay (the team decides later) but say so in extra, which the chunker never reads."""
    return [_with_extra(b, hidden=True) if _slide(b) in hidden else b for b in blocks]


def _with_extra(block: Block, **extra: object) -> Block:
    return Block.model_validate({**block.model_dump(), "extra": {**block.extra, **extra}})


def _picture_only_slides(doc: "DoclingDocument", blocks: list[Block]) -> list[str]:
    """Name for the teacher each slide with a picture or a chart whose only text, if any, is its title.

    A title is a heading, and headings add no text to a chunk; a "[Figure]" block holds no words to search for. So
    such a slide answers nothing until its pictures are described. Icons don't count: a title and a small logo is a
    section slide, not a missing figure.
    """
    with_text = {_slide(b) for b in blocks if b.kind not in ("heading", "figure")}
    with_picture = {prov.page_no for picture in doc.pictures if not _icon(picture) for prov in picture.prov}
    silent = sorted(with_picture - with_text)
    return [messages.no_text_units(SLIDES, silent)] if silent else []


def _picture(doc: "DoclingDocument", figure_id: str | None):
    """The Docling picture a figure_id names: "fig7" is doc.pictures[7] (docling_blocks.figure_name())."""
    return doc.pictures[int((figure_id or "").removeprefix("fig"))]


def _icon(picture) -> bool:
    """Shown under 48 points on both sides, to_blocks()'s rule; without a position, its size in pixels decides."""
    sizes = [(abs(p.bbox.r - p.bbox.l) / EMU_PER_POINT, abs(p.bbox.t - p.bbox.b) / EMU_PER_POINT)
             for p in picture.prov]
    if not sizes and picture.image is not None:
        sizes = [(picture.image.size.width, picture.image.size.height)]
    return bool(sizes) and all(width < ICON_SIDE_PT and height < ICON_SIDE_PT for width, height in sizes)


def _slide(block: Block) -> int:
    """The block's slide number. to_blocks() always sets it for pptx, so a missing one is a bug, not a bad file."""
    if block.loc.slide is None:
        raise ValueError(f"block {block.seq} has no slide number")
    return block.loc.slide