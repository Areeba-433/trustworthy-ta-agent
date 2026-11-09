"""Run the current PPTX extractor on every script-made fixture deck: what survives, as counts and yes/no only.

    python -m scripts.pptx_gap_check

The extractor runs exactly as an upload does, through pipeline.process() (pre-check, Docling, the PPTX loader,
the PPTX chunker), with the data folder pointed at a temporary folder, so nothing is written into the repo. No slide
text is printed: checks compare blocks with the fixtures' own made-up labels and print only counts. Errors logged
during a run are shown by type only, because a message could quote a block.
"""
from __future__ import annotations

import logging
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.shapes.group import GroupShape
from pptx.shapes.picture import Picture

from app.core.config import settings
from app.ingestion.cleaning.common import title_from_filename
from tests.ingestion.pptx_fixtures import BUILDERS, MIXED_SLIDES, TEXTS, census, write_deck

SHORT = {"heading": "H", "paragraph": "P", "list_item": "L", "table": "T", "caption": "C", "figure_text": "FT",
         "slide_notes": "N", "code": "Co", "formula": "Fo", "figure": "F", "transcript": "Tr"}
FIGURE_KINDS = {"figure", "figure_text", "caption"}      # blocks keeping a figure's trace ("figure" comes in 2.1)
TITLED = {"title_bullets", "with_notes", "picture_only", "flowchart", "loose_shapes", "grouped", "table", "chart",
          "hidden_slide", "repeated_logo", "tiny_icon"}   # fixtures whose slides have a title
HAS_NOTES = {"with_notes", "hidden_slide", "repeated_logo", "title_bullets+with_notes"}


class TypesOnly(logging.Handler):
    """Keeps the type of every error logged during a run, never its message."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.seen: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        kind = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else "error"
        self.seen.append(f"{kind} in {record.msg.split(':')[0]}")


def run(path: Path, resource_id: str) -> tuple[Any, list[str]]:
    from app.ingestion.pipeline import process

    log = logging.getLogger("tta.ingestion")
    handler, propagate = TypesOnly(), log.propagate
    log.addHandler(handler)
    log.propagate = False                                  # tracebacks stay off the screen
    try:
        return process(path, resource_id, "gap_check"), handler.seen
    finally:
        log.removeHandler(handler)
        log.propagate = propagate


# ================================================================ small measures over blocks and chunks

def found(texts: list[str], blocks: list) -> int:
    joined = "\n".join(b.text for b in blocks)
    return sum(text in joined for text in texts)


def pictures_on(shapes: Any) -> int:
    """Pictures on one slide, inside groups and placeholders too."""
    return sum(pictures_on(s.shapes) if isinstance(s, GroupShape) else isinstance(s, Picture) for s in shapes)


def yes(flag: bool) -> str:
    return "yes" if flag else "no"


def traces(blocks: list) -> int:
    """Distinct figure ids (contract 2.1) plus figure-like blocks without one."""
    ids = {getattr(b, "figure_id", None) for b in blocks} - {None}
    return len(ids) + sum(b.kind in FIGURE_KINDS and getattr(b, "figure_id", None) is None for b in blocks)


def kinds(blocks: list) -> str:
    counts = Counter(SHORT.get(b.kind, b.kind) for b in blocks)
    return " ".join(f"{k}{n}" for k, n in counts.items()) or "-"


def chunks_on(chunked: Any, slide: int) -> list:
    return [c for c in (chunked.chunks if chunked is not None else []) if c.loc.slide == slide]


def notes_with_slide(blocks: list, chunked: Any, slide: int) -> str:
    notes = [b for b in blocks if b.kind == "slide_notes"]
    if not notes:
        return "missing"
    together = [c for c in chunks_on(chunked, slide) if notes[0].seq in c.block_seqs
                and any(s != notes[0].seq for s in c.block_seqs)]
    return "with slide" if together else "own chunk" if chunks_on(chunked, slide) else "no chunk"


def order_kept(blocks: list) -> bool:
    joined = "\n".join(b.text for b in blocks)
    places = [joined.find(text) for text in TEXTS["order"]]
    return -1 not in places and places == sorted(places)


CHECKS: dict[str, Callable[[list, Any, int], str]] = {
    "title_bullets": lambda b, c, s: f"bullets {found(TEXTS['bullets'], b)}/4",
    "with_notes": lambda b, c, s: f"notes {notes_with_slide(b, c, s)}",
    "picture_only": lambda b, c, s: f"slide has a chunk {yes(bool(chunks_on(c, s)))}",
    "picture_caption": lambda b, c, s: "caption block kind "
                                      + next((x.kind for x in b if TEXTS["caption"] in x.text), "missing"),
    "flowchart": lambda b, c, s: f"box words {found(TEXTS['boxes'], b)}/3, arrows recorded 0/2",
    "loose_shapes": lambda b, c, s: f"shape words {found(TEXTS['shapes'], b)}/3",
    "grouped": lambda b, c, s: f"group words {found(TEXTS['grouped'], b)}/3",
    "table": lambda b, c, s: f"table blocks {sum(x.kind == 'table' for x in b)}, "
                             f"cells {found([t for row in TEXTS['table'] for t in row], b)}/9",
    "chart": lambda b, c, s: f"chart words {found(TEXTS['chart']['categories'] + TEXTS['chart']['series'], b)}/5",
    "no_title": lambda b, c, s: "",
    "empty_slide": lambda b, c, s: "",
    "hidden_slide": lambda b, c, s: f"slide kept {yes(bool(b))}, marked hidden no",
    "repeated_logo": lambda b, c, s: "",
    "tiny_icon": lambda b, c, s: "",
    "reading_order": lambda b, c, s: f"order kept {yes(order_kept(b))}",
}


def path_check(blocks: list, deck_title: str, titled: bool) -> str:
    if not blocks:
        return "-"
    if any(b.heading_path[0] != deck_title for b in blocks):
        return "BAD start"
    if titled and any(b.heading_path[1:2] != [TEXTS["title"]] for b in blocks):
        return "no slide title"
    return "ok" if titled else "deck only"


# ================================================================ one row per fixture, then the mixed deck by slide

def fixture_row(name: str, path: Path) -> str:
    result, errors = run(path, f"gap_{name}")
    parsed, chunked = getattr(result, "parsed", None), getattr(result, "chunked", None)
    blocks = parsed.blocks if parsed is not None else []
    deck = Presentation(str(path))
    pictures = census(deck).pictures
    slides = len(deck.slides)
    no_chunk = sorted({b.loc.slide for b in blocks} - {c.loc.slide for c in (chunked.chunks if chunked else [])})
    check = CHECKS[name](blocks, chunked, 1)
    if name in HAS_NOTES and name != "with_notes":
        check = ", ".join(filter(None, [check, f"notes {notes_with_slide(blocks, chunked, 1)}"]))
    cells = [name, getattr(result, "status", "?"), f"{len(blocks)} {kinds(blocks)}",
             yes(all(b.loc.slide is not None for b in blocks)) if blocks else "-",
             path_check(blocks, title_from_filename(path.name), name in TITLED),
             str(len(chunked.chunks)) if chunked else "0", ",".join(map(str, no_chunk)) or "-",
             f"{traces(blocks)}/{pictures}", f"{slides}",
             check + (f" | logged: {'; '.join(errors)}" if errors else "")]
    return " | ".join(cells)


def mixed_rows(path: Path) -> list[str]:
    result, errors = run(path, "gap_mixed")
    parsed, chunked = getattr(result, "parsed", None), getattr(result, "chunked", None)
    blocks = parsed.blocks if parsed is not None else []
    deck = Presentation(str(path))
    rows = [f"status {getattr(result, 'status', '?')} | blocks {len(blocks)} | chunks "
            f"{len(chunked.chunks) if chunked else 0} | warnings {len(getattr(result, 'warnings', []))}"
            + (f" | logged: {'; '.join(errors)}" if errors else "")]
    for number, ((cases, _), slide) in enumerate(zip(MIXED_SLIDES, deck.slides), start=1):
        on_slide = [b for b in blocks if b.loc.slide == number]
        pictures = pictures_on(slide.shapes)
        checks = [CHECKS[case](on_slide, chunked, number) for case in cases.split("+")]
        rows.append(" | ".join([f"slide {number}", cases, f"{len(on_slide)} {kinds(on_slide)}",
                                path_check(on_slide, title_from_filename(path.name),
                                           not cases.startswith(("picture_caption", "no_title"))),
                                f"chunks {len(chunks_on(chunked, number))}",
                                f"traces {traces(on_slide)}/{pictures}",
                                ", ".join(c for c in checks if c)]))
    return rows


def main() -> int:
    from app.ingestion import converter
    from app.ingestion.contract import CONTRACT_VERSION

    before = settings.INGESTION_DATA_DIR
    with tempfile.TemporaryDirectory(prefix="pptx_gap_", ignore_cleanup_errors=True) as tmp:
        settings.INGESTION_DATA_DIR = str(Path(tmp) / "data")
        try:
            if not converter.cache_file("0" * 64, "pptx").resolve().is_relative_to(Path(tmp).resolve()):
                print("STOP: the Docling cache ignores INGESTION_DATA_DIR and would land in the repo. Nothing ran.")
                return 1
            decks = {name: write_deck(name, Path(tmp) / "decks") for name in BUILDERS}
            print(f"contract {CONTRACT_VERSION}")
            print("fixture | status | blocks | slide# on all | heading_path | chunks | slides w/o chunk | "
                  "figure traces/pictures | slides | check")
            for name in BUILDERS:
                if name != "mixed_deck":
                    print(fixture_row(name, decks[name]))
            print("\nmixed_deck")
            print("\n".join(mixed_rows(decks["mixed_deck"])))
        finally:
            settings.INGESTION_DATA_DIR = before
    return 0


if __name__ == "__main__":
    sys.exit(main())