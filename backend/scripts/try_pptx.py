"""Numbers about one PowerPoint deck for step 0 of the figures plan. Prints NUMBERS ONLY, never slide text.

    python -m scripts.try_pptx <deck.pptx>
    python -m scripts.try_pptx <deck.pptx> --no-classifier --no-libreoffice     # fast: python-pptx and Docling only

Nothing is written into the repo: Docling's cache, LibreOffice's PDF and LibreOffice's profile live in one temporary
folder, deleted at the end. The deck's file name is not printed either (a short hash stands for it), so the output
can be pasted into a PR. Errors print their type only, because a message could quote the deck.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.shapes.autoshape import Shape
from pptx.shapes.connector import Connector
from pptx.shapes.graphfrm import GraphicFrame
from pptx.shapes.group import GroupShape
from pptx.shapes.picture import Picture

JUNK_SIDE_PX = 64              # figures plan: a picture with either side under 64 px is junk
LOW_TEXT_WORDS = 15            # figures plan: caption + nearby text under 15 words is "low-text"
DECORATION_SHARE = 0.5         # figures plan: the same hash on more than half the slides is template decoration
JUNK_LABELS = {"logo", "icon"}                       # figures plan: classifier labels dropped as junk
DIAGRAM_MIN_SHAPES = 3         # figures plan: 1+ connector or 3+ drawn shapes means "draw the whole slide"
DRAWN = {MSO_SHAPE_TYPE.AUTO_SHAPE, MSO_SHAPE_TYPE.FREEFORM}
SMARTART_PART = re.compile(r"^ppt/diagrams/data\d+\.xml$")
DIAGRAM_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
WORD = re.compile(r"\w+")
LIBREOFFICE_TIMEOUT = 600      # seconds per conversion: a safety net, not a target
SOFFICE_PLACES = [r"C:\Program Files\LibreOffice\program\soffice.exe",
                  r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                  "/Applications/LibreOffice.app/Contents/MacOS/soffice", "/usr/bin/soffice"]


# ================================================================ what python-pptx sees

@dataclass
class Pic:
    slide: int
    index: int                 # 1-based in shape order on its slide, groups included
    width: int
    height: int
    sha256: str
    pixels: str                # hash of the decoded pixels: matches Docling's re-encoded copy of the same picture
    in_group: bool
    placeholder: bool
    words_around: int = 0      # slide title + every other text on the slide (notes not counted)
    label_pptx: str = "-"      # Docling's label on the PPTX, or "-"
    label_pdf: str = "-"       # Docling's label on the LibreOffice PDF of the deck, or "-"
    in_docling: bool = False


@dataclass
class SlideFacts:
    number: int
    hidden: bool = False
    has_notes: bool = False
    words: int = 0
    connectors: int = 0
    drawn: int = 0
    drawn_with_text: int = 0
    groups: int = 0
    tables: int = 0
    charts: int = 0
    smartart_frames: int = 0
    pictures: list[Pic] = field(default_factory=list)
    linked_pictures: int = 0   # pictures whose bytes live outside the file

    @property
    def diagram_rule(self) -> bool:
        return self.connectors >= 1 or self.drawn >= DIAGRAM_MIN_SHAPES


def _walk(shapes: Any, in_group: bool = False):
    for shape in shapes:
        yield shape, in_group
        if isinstance(shape, GroupShape):
            yield from _walk(shape.shapes, in_group=True)


def _words(shape: Any) -> int:
    count = 0
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        count += len(WORD.findall(shape.text_frame.text))
    if isinstance(shape, GraphicFrame) and shape.has_table:
        count += sum(len(WORD.findall(cell.text)) for row in shape.table.rows for cell in row.cells)
    return count


def pixel_hash(blob: bytes) -> tuple[int, int, str]:
    with Image.open(io.BytesIO(blob)) as image:
        rgba = image.convert("RGBA")
        return rgba.width, rgba.height, hashlib.sha256(rgba.tobytes()).hexdigest()


def read_slides(path: Path) -> list[SlideFacts]:
    deck = Presentation(str(path))
    slides = []
    for number, slide in enumerate(deck.slides, start=1):       # Docling's numbering: hidden slides count
        facts = SlideFacts(number, hidden=slide._element.get("show") == "0")
        notes = slide.notes_slide.notes_text_frame if slide.has_notes_slide else None
        facts.has_notes = bool(notes is not None and notes.text.strip())
        index = 0
        for shape, in_group in _walk(slide.shapes):
            facts.words += _words(shape)
            if isinstance(shape, Picture):
                index += 1
                try:
                    blob = shape.image.blob
                except Exception:                                  # a linked picture: no bytes in the file
                    facts.linked_pictures += 1
                    continue
                try:
                    width, height, pixels = pixel_hash(blob)
                except Exception:                                  # EMF/WMF off Windows, or a damaged picture
                    width, height, pixels = 0, 0, "-"
                facts.pictures.append(Pic(number, index, width, height, hashlib.sha256(blob).hexdigest(), pixels,
                                          in_group, shape.is_placeholder))
            elif isinstance(shape, Connector):
                facts.connectors += 1
            elif isinstance(shape, GroupShape):
                facts.groups += 1
            elif isinstance(shape, GraphicFrame):
                facts.tables += shape.has_table
                facts.charts += shape.has_chart
                data = shape._element.find(f".//{qn('a:graphicData')}")
                facts.smartart_frames += data is not None and data.get("uri") == DIAGRAM_URI
            elif isinstance(shape, Shape) and shape.shape_type in DRAWN:
                facts.drawn += 1
                facts.drawn_with_text += _words(shape) > 0
        for pic in facts.pictures:
            pic.words_around = facts.words
        slides.append(facts)
    return slides


def smartart_parts(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(bool(SMARTART_PART.match(name)) for name in archive.namelist())


# ================================================================ what Docling sees

class CacheOutsideTemp(RuntimeError):
    """The team's cache path ignores INGESTION_DATA_DIR: stop before Docling writes into the repo."""


@dataclass
class DoclingPic:
    slide: int | None
    pixels: str | None         # None: no picture stored (charts, metafiles without LibreOffice)
    label: str | None


def _label(item: Any) -> str | None:
    meta = getattr(item, "meta", None)
    classification = getattr(meta, "classification", None) if meta is not None else None
    return classification.get_main_prediction().class_name if classification is not None else None


def docling_pictures(doc: Any) -> list[DoclingPic]:
    found = []
    for item in doc.pictures:
        slide = item.prov[0].page_no if item.prov else None
        image = item.get_image(doc)
        pixels = hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest() if image is not None else None
        found.append(DoclingPic(slide, pixels, _label(item)))
    return found


def parse_with_team_converter(path: Path, data_dir: Path) -> dict[str, Any]:
    """The team's converter, twice: the first run reads the deck, the second should come from the cache."""
    from app.core.config import settings

    before = settings.INGESTION_DATA_DIR
    settings.INGESTION_DATA_DIR = str(data_dir)           # the cache goes to the temporary folder, not the repo
    try:
        start = time.perf_counter()
        from app.ingestion import converter               # imported here: the import is part of a cold start
        imported = time.perf_counter() - start
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if not converter.cache_file(sha, "pptx").resolve().is_relative_to(data_dir.resolve()):
            raise CacheOutsideTemp
        runs = []
        for _ in range(2):
            start = time.perf_counter()
            result = converter.convert(path, "pptx", sha)
            runs.append((time.perf_counter() - start, result.from_cache))
    finally:
        settings.INGESTION_DATA_DIR = before
    return {"import": imported, "runs": runs, "document": result.document}


def classify(path: Path, fmt: str) -> tuple[list[DoclingPic], float]:
    """Docling with its picture classifier switched on (it is off in the team's converter, for PPTX and PDF)."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import ConvertPipelineOptions, PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption, PowerpointFormatOption

    if fmt == "pptx":
        option = PowerpointFormatOption(pipeline_options=ConvertPipelineOptions(do_picture_classification=True))
        allowed = InputFormat.PPTX
    else:
        option = PdfFormatOption(pipeline_options=PdfPipelineOptions(
            do_ocr=False, do_table_structure=False, do_picture_classification=True,
            generate_picture_images=True, images_scale=2.0))
        allowed = InputFormat.PDF
    start = time.perf_counter()
    result = DocumentConverter(allowed_formats=[allowed], format_options={allowed: option}).convert(path)
    return docling_pictures(result.document), time.perf_counter() - start


# ================================================================ LibreOffice

def find_soffice() -> str | None:
    for candidate in [os.environ.get("SOFFICE"), shutil.which("soffice"), shutil.which("libreoffice"),
                      *SOFFICE_PLACES]:
        if candidate and Path(candidate).exists():
            console = Path(candidate).with_name("soffice.com")    # Windows: this launcher waits for the end
            return str(console) if console.exists() else candidate
    return None


def libreoffice_pdf(path: Path, work: Path, soffice: str) -> tuple[list[float], Path | None]:
    """Two conversions with one fresh profile: the first pays LibreOffice's cold start, the second does not."""
    profile = (work / "lo_profile").as_uri()
    out = work / "pdf"
    times = []
    for _ in range(2):
        start = time.perf_counter()
        subprocess.run([soffice, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
                        "--outdir", str(out), str(path)], capture_output=True, timeout=LIBREOFFICE_TIMEOUT)
        times.append(time.perf_counter() - start)
    pdf = out / f"{path.stem}.pdf"
    return times, pdf if pdf.exists() else None


def pdf_pages(pdf: Path) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    try:
        return len(document)
    finally:
        document.close()


# ================================================================ putting it together

def match(pics: list[Pic], found: list[DoclingPic], attribute: str) -> None:
    """Give each python-pptx picture the label of the Docling picture with the same pixels on the same slide."""
    by_key = {(d.slide, d.pixels): d for d in found if d.pixels}
    for pic in pics:
        hit = by_key.get((pic.slide, pic.pixels))
        if hit is not None:
            if attribute == "label_pptx":
                pic.in_docling = True
            setattr(pic, attribute, hit.label or "-")


def page_to_slide(slides: list[SlideFacts], pages: int) -> dict[int, int] | None:
    """LibreOffice leaves hidden slides out of the PDF by default: map pages back to slide numbers."""
    if pages == len(slides):
        return {n: n for n in range(1, pages + 1)}
    visible = [s.number for s in slides if not s.hidden]
    return {page: slide for page, slide in enumerate(visible, start=1)} if pages == len(visible) else None


def measure(path: Path, classifier: bool = True, libreoffice: bool = True, pdf_compare: bool = True) -> dict:
    """Everything the report prints, as numbers. No slide text ever enters the result."""
    report: dict[str, Any] = {"deck": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
                              "kb": path.stat().st_size // 1024, "notes": []}
    slides = read_slides(path)
    pics = [pic for slide in slides for pic in slide.pictures]
    report.update(slides=slides, pictures=pics, smartart_parts=smartart_parts(path))
    with tempfile.TemporaryDirectory(prefix="try_pptx_", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        try:
            parsed = parse_with_team_converter(path, work / "data")
            report["docling"] = {"import": parsed["import"], "runs": parsed["runs"]}
            report["docling_pics"] = docling_pictures(parsed["document"])
            match(pics, report["docling_pics"], "label_pptx")
        except Exception as exc:
            report["notes"].append(f"team converter unavailable: {type(exc).__name__}")
        if classifier:
            try:
                found, seconds = classify(path, "pptx")
                labels = Counter(d.label for d in found if d.label)
                report["classifier_pptx"] = {"seconds": seconds, "labels": labels}
                match(pics, found, "label_pptx")
            except Exception as exc:
                report["notes"].append(f"classifier on PPTX unavailable: {type(exc).__name__}")
        soffice = find_soffice() if libreoffice else None
        if libreoffice and soffice is None:
            report["notes"].append("LibreOffice not found: set SOFFICE to soffice's full path, or install it")
        if soffice is not None:
            times, pdf = libreoffice_pdf(path, work, soffice)
            report["libreoffice"] = {"seconds": times, "pdf_pages": pdf_pages(pdf) if pdf else 0}
            if pdf is not None and classifier and pdf_compare:
                try:
                    found, seconds = classify(pdf, "pdf")
                    mapping = page_to_slide(slides, report["libreoffice"]["pdf_pages"]) or {}
                    for d in found:
                        d.slide = mapping.get(d.slide or 0)
                    report["classifier_pdf"] = {"seconds": seconds, "pictures": len(found),
                                                "labels": Counter(d.label for d in found if d.label),
                                                "per_slide": Counter(d.slide for d in found)}
                except Exception as exc:
                    report["notes"].append(f"classifier on the PDF unavailable: {type(exc).__name__}")
    return report


def junk(pic: Pic, repeated: set[str]) -> bool:
    return (min(pic.width, pic.height) < JUNK_SIDE_PX or pic.sha256 in repeated
            or pic.label_pptx in JUNK_LABELS)


def lines(report: dict) -> list[str]:
    slides: list[SlideFacts] = report["slides"]
    pics: list[Pic] = report["pictures"]
    out = [f"deck {report['deck']} ({report['kb']} KB)", "", "== pictures (python-pptx), one per line",
           "slide  pic  width x height  group  placeholder  in_docling  label_pptx        label_pdf         words"]
    for p in pics:
        out.append(f"{p.slide:>5}  {p.index:>3}  {p.width:>5} x {p.height:<6}  {'yes' if p.in_group else 'no':<5}  "
                   f"{'yes' if p.placeholder else 'no':<11}  {'yes' if p.in_docling else 'no':<10}  "
                   f"{p.label_pptx:<16}  {p.label_pdf:<16}  {p.words_around:>5}")
    on_slides = defaultdict(set)
    for p in pics:
        on_slides[p.sha256].add(p.slide)
    repeated = {sha for sha, where in on_slides.items() if len(where) > DECORATION_SHARE * len(slides)}
    out += ["", "== 1. counts",
            f"slides {len(slides)} | pictures {len(pics)} | "
            f"linked pictures {sum(s.linked_pictures for s in slides)} | "
            f"tables {sum(s.tables for s in slides)} | charts {sum(s.charts for s in slides)} | "
            f"connectors {sum(s.connectors for s in slides)} | group shapes {sum(s.groups for s in slides)} | "
            f"drawn shapes {sum(s.drawn for s in slides)}",
            f"SmartArt parts {report['smartart_parts']} (frames {sum(s.smartart_frames for s in slides)}) | "
            f"slides with notes {sum(s.has_notes for s in slides)} | "
            f"hidden slides {sum(s.hidden for s in slides)} | pictures in groups {sum(p.in_group for p in pics)} | "
            f"in placeholders {sum(p.placeholder for p in pics)}"]
    out += ["", "== 2. Docling's picture labels"]
    team = Counter(d.label for d in report.get("docling_pics", []) if d.label)
    out.append(f"team converter (classifier off): {sum(team.values())} labelled {dict(team) or ''}".rstrip())
    if "classifier_pptx" in report:
        c = report["classifier_pptx"]
        out.append(f"PPTX, classifier on: {sum(c['labels'].values())} labelled {dict(c['labels'])} "
                   f"({c['seconds']:.1f} s)")
    if "classifier_pdf" in report:
        c = report["classifier_pdf"]
        out.append(f"PDF of the deck, classifier on: {c['pictures']} pictures, "
                   f"{sum(c['labels'].values())} labelled {dict(c['labels'])} ({c['seconds']:.1f} s)")
        both = [p for p in pics if p.label_pptx != "-" and p.label_pdf != "-"]
        out.append(f"pictures labelled on both paths: {len(both)} | labels differ: "
                   f"{sum(p.label_pptx != p.label_pdf for p in both)}")
    out += ["", "== 3. python-pptx vs Docling pictures"]
    if "docling_pics" in report:
        with_image = Counter(d.slide for d in report["docling_pics"] if d.pixels)
        without = Counter(d.slide for d in report["docling_pics"] if not d.pixels)
        ours = Counter(p.slide for p in pics)
        out.append(f"python-pptx {len(pics)} | Docling {sum(with_image.values())} with a picture stored, "
                   f"{sum(without.values())} without (charts, metafiles) | matched by pixels "
                   f"{sum(p.in_docling for p in pics)}")
        for s in slides:
            if ours[s.number] != with_image[s.number]:
                reasons = [f"{sum(p.placeholder for p in s.pictures)} in placeholders",
                           f"{sum(p.in_group for p in s.pictures)} in groups", f"{s.linked_pictures} linked"]
                out.append(f"  MISMATCH slide {s.number}: python-pptx {ours[s.number]}, Docling "
                           f"{with_image[s.number]} ({', '.join(reasons)})")
    out += ["", "== 4. pictures repeated on more than half the slides"]
    out.append(f"{len(repeated)} hash(es)" + "".join(f" | {sha[:8]} on {len(on_slides[sha])} slides"
                                                     for sha in sorted(repeated)))
    by_pixels = defaultdict(set)
    for p in pics:
        if p.pixels != "-":
            by_pixels[p.pixels].add(p.slide)
    out.append(f"pictures on 2+ slides: {sum(len(w) > 1 for w in on_slides.values())} by file bytes, "
               f"{sum(len(w) > 1 for w in by_pixels.values())} by pixels")
    kept = [p for p in pics if not junk(p, repeated)]
    out += ["", "== 5. words around pictures",
            f"under {LOW_TEXT_WORDS} words: {_share(pics)} of all pictures | {_share(kept)} of pictures kept "
            f"after the junk rules ({len(kept)} kept, {len(pics) - len(kept)} junk; "
            f"{sum(min(p.width, p.height) < JUNK_SIDE_PX for p in pics)} under {JUNK_SIDE_PX} px)"]
    if pics:
        out.append(f"words per picture: min {min(p.words_around for p in pics)}, median "
                   f"{statistics.median(p.words_around for p in pics):g}, max {max(p.words_around for p in pics)}")
    diagram = [s.number for s in slides if s.diagram_rule]
    chart = [s.number for s in slides if s.charts]
    out += ["", "== 6. slides to draw whole",
            f"diagram rule (>=1 connector or >={DIAGRAM_MIN_SHAPES} drawn shapes): {len(diagram)} slides {diagram}",
            f"slides with a chart: {len(chart)} {chart} | either: {len(set(diagram) | set(chart))}",
            f"diagram rule on visible slides: {sum(not slides[n - 1].hidden for n in diagram)} | "
            f"slides with a connector: {sum(s.connectors > 0 for s in slides)}"]
    out += [f"  slide {s.number}{' (hidden)' if s.hidden else ''}: connectors {s.connectors}, drawn {s.drawn} "
            f"({s.drawn_with_text} holding text), pictures {len(s.pictures)}" for s in slides if s.diagram_rule]
    out += ["", "== 7. Docling parse time (team converter)"]
    if "docling" in report:
        d = report["docling"]
        (first, hit1), (second, hit2) = d["runs"]
        out.append(f"import {d['import']:.1f} s | run 1 {first:.2f} s (from cache: {hit1}) | "
                   f"run 2 {second:.2f} s (from cache: {hit2})")
    out += ["", "== 8. LibreOffice to PDF"]
    if "libreoffice" in report:
        lo = report["libreoffice"]
        cold, warm = lo["seconds"]
        visible = sum(not s.hidden for s in slides)
        out.append(f"run 1 (cold) {cold:.1f} s, {cold / max(len(slides), 1):.2f} s per slide | run 2 {warm:.1f} s, "
                   f"{warm / max(len(slides), 1):.2f} s per slide")
        out.append(f"PDF pages {lo['pdf_pages']} | slides {len(slides)} | visible slides {visible}"
                   + (" | hidden slides are missing from the PDF: page numbers shift" if lo["pdf_pages"] == visible
                      < len(slides) else ""))
    out += [f"NOTE {note}" for note in report["notes"]]
    return out


def _share(pics: list[Pic]) -> str:
    if not pics:
        return "0/0"
    low = sum(p.words_around < LOW_TEXT_WORDS for p in pics)
    return f"{low}/{len(pics)} ({low / len(pics):.0%})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Numbers about a PowerPoint deck (prints no slide text).")
    parser.add_argument("deck", type=Path)
    parser.add_argument("--no-classifier", action="store_true", help="skip Docling's picture classifier")
    parser.add_argument("--no-libreoffice", action="store_true", help="skip the LibreOffice timing")
    parser.add_argument("--no-pdf", action="store_true", help="skip classifying the LibreOffice PDF")
    args = parser.parse_args(argv)
    if not args.deck.is_file() or args.deck.suffix.lower() != ".pptx":
        parser.error("give a .pptx file")
        return 2
    report = measure(args.deck, classifier=not args.no_classifier, libreoffice=not args.no_libreoffice,
                     pdf_compare=not args.no_pdf)
    print("\n".join(lines(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())