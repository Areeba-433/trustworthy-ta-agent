"""One Markdown review file per deck: what python-pptx sees on each slide, next to what the pipeline keeps.

    python -m scripts.pptx_review_md <deck.pptx or folder> --out <folder>

THESE FILES HOLD COURSE TEXT. They are written only under the system temp folder, or under backend/data/ when git
confirms the folder is ignored; any other --out is refused. Read them; never paste or commit them. The console
prints numbers only, and each file is named after a short hash of its deck, not the deck's name.

The raw half reads the slide XML itself (python-pptx and lxml) and shares no code with the loader, so it shows
what the loader missed. The pipeline half runs pipeline.process() as an upload does, with the data folder pointed
at a temporary folder. The output has no timings or temp paths, so two runs can be compared with git diff.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import logging
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from lxml import etree

from app.core.config import settings

BACKEND = Path(__file__).resolve().parents[1]
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "a14": "http://schemas.microsoft.com/office/drawing/2010/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
}
FRAMES = {"http://schemas.openxmlformats.org/drawingml/2006/table": "table",
          "http://schemas.openxmlformats.org/drawingml/2006/chart": "chart",
          "http://schemas.openxmlformats.org/drawingml/2006/diagram": "smartart",
          "http://schemas.openxmlformats.org/presentationml/2006/ole": "embedded object"}
MONOSPACE = {"courier new", "courier", "consolas", "lucida console", "menlo", "monaco", "source code pro"}
FIGURE_KINDS = {"figure", "figure_text", "caption"}
CHECKLIST = """\
> **Contains course text: read it, never paste or commit it.**
> Raw = python-pptx's view of the slide XML. Pipeline = what an upload keeps. Flags are computed, not judged.

Review checklist, per slide (tick in your head, note slide numbers):
- [ ] Formulas: every `[equation: ...]` in raw is in pipeline (after 1.7, as a `formula` block).
- [ ] Arrows / flow meaning: connectors in raw; does the pipeline text still make sense without them?
- [ ] Missing text: every raw line appears in a pipeline block (or is a footer, slide number or date).
- [ ] Reading order: pipeline order matches how the slide reads.
- [ ] Bullet levels: raw indents by level; pipeline writes every bullet as "- " (known, out of scope).
- [ ] Superscripts/subscripts/Greek: raw shows ^{..}, _{..}, <Symbol:..>; check the pipeline's version.
- [ ] Code indentation: raw keeps leading spaces in (monospace) shapes; pipeline drops them (known).
- [ ] Notes: raw notes are in a `slide_notes` block of the same slide.
- [ ] Tables: every cell in raw is in the pipeline's table.
"""


def _q(name: str) -> str:
    prefix, local = name.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _local(element: Any) -> str:
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


# ================================================================ where the files may go

def checked_out(out: Path) -> Path:
    target = out.expanduser().resolve()
    temp, data = Path(tempfile.gettempdir()).resolve(), (BACKEND / "data").resolve()
    if not (target.is_relative_to(temp) or target.is_relative_to(data)):
        sys.exit(f"refused: --out must be inside {temp} or {data}")
    if target.is_relative_to(BACKEND.parent.resolve()):            # inside the repo: git must ignore it
        try:
            probe = subprocess.run(["git", "-C", str(BACKEND), "check-ignore", "-q", str(target / "probe.md")],
                                   capture_output=True)
            ignored = probe.returncode == 0
        except OSError:
            ignored = False
        if not ignored:
            sys.exit("refused: git would track files there, or git is missing. Use the temp folder.")
    if target.exists() and not target.is_dir():
        sys.exit("refused: --out is a file")
    return target


# ================================================================ raw: the slide XML, read here and only here

def _paragraph(p: Any) -> str:
    out = []
    for child in p:
        name = _local(child)
        if name == "r":
            text = "".join(t.text or "" for t in child.iter(_q("a:t")))
            props = child.find(_q("a:rPr"))
            if props is not None:
                fonts = {(e.get("typeface") or "").lower() for e in props if _local(e) in ("latin", "sym", "cs")}
                if any("symbol" in f for f in fonts):
                    text = f"<Symbol:{text}>"
                baseline = int(props.get("baseline", "0") or 0)
                text = f"^{{{text}}}" if baseline > 0 else f"_{{{text}}}" if baseline < 0 else text
            out.append(text)
        elif name == "fld":
            out.append("".join(t.text or "" for t in child.iter(_q("a:t"))))
        elif name == "br":
            out.append(" ↵ ")
        elif child.tag == _q("a14:m"):
            out.append("[equation: " + " ".join(t.text for t in child.iter(_q("m:t")) if t.text) + "]")
    return "".join(out)


def _monospace(element: Any) -> bool:
    return any((e.get("typeface") or "").lower() in MONOSPACE for e in element.iter(_q("a:latin")))


def _walk(container: Any, alternate: bool = False):
    for child in container:
        name = _local(child)
        if name in ("", "nvGrpSpPr", "grpSpPr", "extLst"):
            continue
        if name == "grpSp":
            yield "group", child, alternate
            yield from _walk(child, alternate)
        elif name == "AlternateContent":
            branch = child.find(_q("mc:Choice"))
            branch = branch if branch is not None else child.find(_q("mc:Fallback"))
            if branch is not None:
                yield from _walk(branch, True)
        else:
            yield name, child, alternate


def raw_slide(slide: Any) -> tuple[list[str], Counter]:
    lines: list[str] = []
    counts: Counter = Counter()
    for index, (name, element, alternate) in enumerate(_walk(slide.shapes._spTree), start=1):
        where = " [inside mc:AlternateContent: Docling never sees it]" if alternate else ""
        if name == "group":
            lines.append(f"[{index}] group")
            continue
        if name == "sp":
            ph = element.find(f"{_q('p:nvSpPr')}/{_q('p:nvPr')}/{_q('p:ph')}")
            box = element.find(f"{_q('p:nvSpPr')}/{_q('p:cNvSpPr')}")
            label = (f"placeholder {ph.get('type', 'obj')}" if ph is not None else
                     "text box" if box is not None and box.get("txBox") in ("1", "true") else "shape")
            if element.find(f"{_q('p:spPr')}/{_q('a:blipFill')}") is not None:
                label += ", picture fill"
                counts["pictures"] += 1
            lines.append(f"[{index}] {label}{' (monospace)' if _monospace(element) else ''}{where}")
            for p in element.iterfind(f"{_q('p:txBody')}/{_q('a:p')}"):
                text = _paragraph(p)
                if text.strip():
                    props = p.find(_q("a:pPr"))
                    level = int(props.get("lvl", "0")) if props is not None else 0
                    lines.append("    " + "  " * level + text)
                    counts["text lines"] += 1
                    counts["alternate lines"] += alternate
        elif name == "pic":
            counts["pictures"] += 1
            ph = element.find(f".//{_q('p:ph')}")
            lines.append(f"[{index}] picture {_picture_size(slide, element)}"
                         f"{' in a placeholder' if ph is not None else ''}{where}")
        elif name == "cxnSp":
            counts["connectors"] += 1
            glued = sum(element.find(f".//{_q(tag)}") is not None for tag in ("a:stCxn", "a:endCxn"))
            lines.append(f"[{index}] connector, {glued} of 2 ends glued to shapes{where}")
        elif name == "graphicFrame":
            data = element.find(f"{_q('a:graphic')}/{_q('a:graphicData')}")
            kind = FRAMES.get(data.get("uri") if data is not None else "", "other frame")
            lines.append(f"[{index}] {kind}{where}")
            lines += ["    " + line for line in _frame(slide, element, kind)]
            counts["text lines"] += kind in ("table", "chart", "smartart")
        else:
            lines.append(f"[{index}] {name}{where}")
    counts["equations"] = len(list(slide._element.iter(_q("m:oMath"))))
    title = slide.shapes.title
    heading = title.text_frame.text.replace("\v", " \u21b5 ") if title is not None and title.has_text_frame else ""
    return [f"title: {heading or '(none)'}"] + lines, counts


def _picture_size(slide: Any, element: Any) -> str:
    from PIL import Image

    blip = element.find(f".//{_q('a:blip')}")
    try:
        blob = slide.part.related_part(blip.get(_q("r:embed"))).blob
        with Image.open(io.BytesIO(blob)) as image:
            return f"{image.width}x{image.height} px"
    except Exception:
        return "(size unknown)"


def _frame(slide: Any, element: Any, kind: str) -> list[str]:
    try:
        if kind == "table":
            rows = []
            for row in element.iter(_q("a:tr")):
                cells = [" ".join(_paragraph(p) for p in tc.iterfind(f".//{_q('a:p')}")).strip()
                         for tc in row.iter(_q("a:tc"))]
                rows.append("| " + " | ".join(cells) + " |")
            return rows
        if kind == "chart":
            chart = slide.part.related_part(element.find(f".//{_q('c:chart')}").get(_q("r:id"))).chart
            plot = chart.plots[0] if len(chart.plots) else None
            categories = plot.categories if plot is not None else []
            lines = [f"type {chart.chart_type}", "categories: " + " | ".join(map(str, categories))]
            return lines + [f"series {s.name}: " + " | ".join(map(str, s.values)) for s in chart.series]
        if kind == "smartart":
            relation = element.find(f".//{_q('dgm:relIds')}")
            data = etree.fromstring(slide.part.related_part(relation.get(_q("r:dm"))).blob)
            return [f"point: {_paragraph(p)}" for p in data.iter(_q("a:p")) if _paragraph(p).strip()]
        if kind == "embedded object":
            ole = element.find(f".//{_q('p:oleObj')}")
            return [f"program: {ole.get('progId') if ole is not None else 'unknown'} (no text to read)"]
    except Exception as exc:
        return [f"(could not read: {type(exc).__name__})"]
    return []


# ================================================================ the pipeline, as an upload runs it

class TypesOnly(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.seen: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.seen.append(record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else "error")


def run_pipeline(path: Path, sha: str) -> tuple[Any, list[str]]:
    from app.ingestion.pipeline import process

    log = logging.getLogger("tta.ingestion")
    handler, propagate = TypesOnly(), log.propagate
    log.addHandler(handler)
    log.propagate = False                                    # tracebacks could quote the deck: types only
    try:
        return process(path, f"review_{sha[:12]}", "review"), handler.seen
    finally:
        log.removeHandler(handler)
        log.propagate = propagate


def _fence(lines: list[str]) -> list[str]:
    body = "\n".join(lines) or "(nothing)"
    fence = "~" * max(3, max((len(m) for m in re.findall(r"~+", body)), default=0) + 1)
    return [fence + "text", body, fence]


def review(path: Path) -> tuple[str, dict[str, int]]:
    from pptx import Presentation

    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    result, errors = run_pipeline(path, sha)
    parsed, chunked = getattr(result, "parsed", None), getattr(result, "chunked", None)
    blocks = parsed.blocks if parsed is not None else []
    chunks = chunked.chunks if chunked is not None else []
    deck = Presentation(str(path))                               # the zip is read once for the raw half
    totals: Counter = Counter()
    out = [f"# Review of {path.name}", "", f"deck {sha[:12]} | slides {len(deck.slides)} | "
           f"status {getattr(result, 'status', '?')} | blocks {len(blocks)} | chunks {len(chunks)}"]
    out += [f"teacher message: {w}" for w in getattr(result, "warnings", [])]
    out += [f"logged error types: {', '.join(errors)}"] if errors else []
    out += ["", CHECKLIST]
    for number, slide in enumerate(deck.slides, start=1):
        hidden = slide._element.get("show") in ("0", "false")
        raw, counts = raw_slide(slide)
        notes = []
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = [_paragraph(p._p) for p in slide.notes_slide.notes_text_frame.paragraphs if p.text.strip()]
        here = [b for b in blocks if b.loc.slide == number]
        chunks_here = [c for c in chunks if c.loc.slide == number]
        traced = (len({getattr(b, "figure_id", None) for b in here} - {None})
                  + sum(b.kind in FIGURE_KINDS for b in here))
        flags = ["HIDDEN"] if hidden else []
        has_text = counts["text lines"] or notes
        flags += ["NO BLOCKS although python-pptx found text"] if has_text and not here else []
        flags += ["NO CHUNK"] if here and not chunks_here else []
        flags += [f"PICTURES {counts['pictures']}, TRACED {traced}"] if counts["pictures"] > traced else []
        flags += [f"EQUATIONS {counts['equations']}"] if counts["equations"] else []
        flags += [f"ALTERNATE-CONTENT LINES {counts['alternate lines']}"] if counts["alternate lines"] else []
        totals.update({"slides": 1, "hidden": int(hidden), "no chunk": int("NO CHUNK" in flags),
                       "no blocks": int(any(f.startswith("NO BLOCKS") for f in flags)),
                       "untraced pictures": max(counts["pictures"] - traced, 0), "equations": counts["equations"],
                       "pictures": counts["pictures"], "connectors": counts["connectors"]})
        out += ["", f"## Slide {number}" + (f" | flags: {', '.join(flags)}" if flags else ""), "",
                f"python-pptx: pictures {counts['pictures']} | connectors {counts['connectors']} | "
                f"equations {counts['equations']} | hidden {'yes' if hidden else 'no'}", "", "### Raw"]
        out += _fence(raw + (["notes:"] + ["    " + n for n in notes] if notes else []))
        out += ["", "### Pipeline"]
        pipeline = [f"block {b.seq:>3} {b.kind:<12} {b.text}" for b in here]
        pipeline += [f"chunk {c.seq:>3} {' > '.join(c.heading_path)} | kinds {', '.join(c.kinds)} | "
                     f"{c.token_count} tokens | blocks {c.block_seqs[0]}-{c.block_seqs[-1]}" for c in chunks_here]
        out += _fence(pipeline)
    totals.update({"blocks": len(blocks), "chunks": len(chunks)})
    return "\n".join(out) + "\n", dict(totals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Markdown review of decks (writes course text; prints numbers).")
    parser.add_argument("target", type=Path, help="a .pptx file or a folder of them")
    parser.add_argument("--out", type=Path, default=Path(tempfile.gettempdir()) / "pptx_review",
                        help="folder for the .md files: under the temp folder or under backend/data/")
    args = parser.parse_args(argv)
    out = checked_out(args.out)
    decks = sorted(args.target.glob("*.pptx")) if args.target.is_dir() else [args.target]
    if not decks or not all(d.is_file() and d.suffix.lower() == ".pptx" for d in decks):
        parser.error("give a .pptx file or a folder holding some")
    from app.ingestion import converter

    before = settings.INGESTION_DATA_DIR
    with tempfile.TemporaryDirectory(prefix="pptx_review_", ignore_cleanup_errors=True) as tmp:
        settings.INGESTION_DATA_DIR = str(Path(tmp) / "data")
        try:
            if not converter.cache_file("0" * 64, "pptx").resolve().is_relative_to(Path(tmp).resolve()):
                print("STOP: the Docling cache ignores INGESTION_DATA_DIR and would land in the repo. Nothing ran.")
                return 1
            out.mkdir(parents=True, exist_ok=True)
            for path in decks:
                text, totals = review(path)
                target = out / f"{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}.md"
                target.write_text(text, encoding="utf-8", newline="\n")
                print(f"{target.stem}: " + " | ".join(f"{k} {v}" for k, v in totals.items()))
        finally:
            settings.INGESTION_DATA_DIR = before
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())