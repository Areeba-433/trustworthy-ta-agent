"""Compare OCR engines on hand-typed pages (Track 2, days 1 to 3). Owner: Minahil.

Set up a folder. Keep it OUT of git if the pages are course material:

    ocr_eval/
      en_lecture3_p2.pdf     en_lecture3_p2.txt      a page and its hand-typed text (UTF-8)
      en_notes_photo.jpg     en_notes_photo.txt
      en_table_scan.png      en_table_scan.txt       type tables row by row, cells separated by spaces
      ur_handout_p1.png      ur_handout_p1.txt       type Urdu with an Urdu keyboard (ک and ی, not ك and ي)
      ur_handout_p2.pdf      ur_handout_p2.txt

The file name starts with its language (en_ or ur_): results are reported per
language. A PDF must hold only the page you typed.

Run from backend/ (needs requirements/docs.txt and requirements/ocr.txt installed):

    python scripts/compare_ocr.py ocr_eval/                      # EasyOCR and Tesseract
    python scripts/compare_ocr.py ocr_eval/ --engines tesseract

For each engine and file it prints the character error rate (CER: share of
characters wrong; lower is better), before and after clean_text(), and the
seconds taken. OCR text is saved in ocr_eval/ocr_output/<engine>/ so you can
read the mistakes, and every number goes to ocr_eval/results.csv. Copy the
averages into docs/ingestion-quality.md and keep the engine with the lower
CER on your material.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
import unicodedata
from pathlib import Path
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.cleaning.common import clean_text  # noqa: E402

PAGE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
LANGUAGES = ("en", "ur")

# Engine name -> Docling OCR options. Both are configured for English + Urdu.
#   easyocr:   pip install easyocr (pin it in requirements/ocr.txt); downloads its models on first run
#   tesseract: the tesseract program on PATH, with eng and urd language data installed
ENGINES = ("easyocr", "tesseract")


# ---------------------------------------------------------------------------
# Character error rate (pure Python; uses jiwer when installed, same result)
# ---------------------------------------------------------------------------

def normalize_for_cer(text: str) -> str:
    """Compare characters, not layout: NFC, and every run of whitespace becomes one space."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance: insertions, deletions and substitutions to turn a into b."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> float:
    reference, hypothesis = normalize_for_cer(reference), normalize_for_cer(hypothesis)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    try:
        import jiwer
        return float(jiwer.cer(reference, hypothesis))
    except ImportError:
        return edit_distance(reference, hypothesis) / len(reference)


def reversed_lines(text: str) -> str:
    """Each line's characters reversed: detects Urdu that comes out in visual (wrong) order."""
    return "\n".join(line[::-1] for line in text.split("\n"))


# ---------------------------------------------------------------------------
# Test set
# ---------------------------------------------------------------------------

def find_pairs(folder: Path) -> list[tuple[Path, Path, str]]:
    """(page file, hand-typed .txt, language) for every page that has a .txt next to it."""
    pairs = []
    for page in sorted(folder.iterdir()):
        if page.suffix.lower() not in PAGE_SUFFIXES:
            continue
        truth = page.with_suffix(".txt")
        lang = page.name.split("_", 1)[0].lower()
        if truth.exists() and lang in LANGUAGES:
            pairs.append((page, truth, lang))
        else:
            print(f"skipped {page.name}: needs {truth.name} and a name starting with en_ or ur_")
    return pairs


# ---------------------------------------------------------------------------
# Docling (imported only when the comparison actually runs)
# ---------------------------------------------------------------------------

def engine_options(engine: str):
    from docling.datamodel.pipeline_options import EasyOcrOptions, TesseractCliOcrOptions
    if engine == "easyocr":
        return EasyOcrOptions(lang=["en", "ur"])
    if engine == "tesseract":
        return TesseractCliOcrOptions(lang=["eng", "urd"])
    raise ValueError(f"unknown engine {engine!r}; choose from {ENGINES}")


def make_converter(engine: str):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = True
    pipeline.ocr_options = engine_options(engine)
    pipeline.ocr_options.force_full_page_ocr = True   # these are scans: read the whole page
    pipeline.do_table_structure = True
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
                        InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline)},
    )
    converter.initialize_pipeline(InputFormat.PDF)   # load the models now, not inside the timing
    return converter


def document_text(doc) -> str:
    """All text Docling found, in reading order; table cells row by row."""
    parts = []
    for item, _level in doc.iterate_items():
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
            continue
        data = getattr(item, "data", None)   # a table
        grid = getattr(data, "grid", None)
        if grid:
            for row in grid:
                parts.append(" ".join(cell.text for cell in row if cell.text))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--engines", nargs="+", choices=ENGINES, default=list(ENGINES))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    pairs = find_pairs(args.folder)
    if not pairs:
        sys.exit("No pages with a hand-typed .txt found. See the instructions at the top of this script.")

    rows = []
    for engine in args.engines:
        started = time.perf_counter()
        converter = make_converter(engine)
        print(f"\n{engine}: models loaded in {time.perf_counter() - started:.1f}s")
        out_dir = args.folder / "ocr_output" / engine
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"{'file':36} {'lang':4} {'CER raw':>8} {'CER clean':>9} {'seconds':>8}  notes")
        for page, truth_file, lang in pairs:
            truth = truth_file.read_text(encoding="utf-8")
            t0 = time.perf_counter()
            result = converter.convert(page, raises_on_error=False)
            seconds = time.perf_counter() - t0
            text = document_text(result.document) if result.document else ""
            (out_dir / f"{page.stem}.txt").write_text(text, encoding="utf-8")

            raw, cleaned = cer(truth, text), cer(truth, clean_text(text))
            notes = []
            if not text.strip():
                notes.append(f"no text ({result.status})")
            if lang == "ur" and text.strip() and cer(truth, reversed_lines(text)) < 0.7 * raw:
                notes.append("Urdu comes out reversed: fix the order in the loader")
            print(f"{page.name[:36]:36} {lang:4} {raw:8.1%} {cleaned:9.1%} {seconds:8.1f}  {'; '.join(notes)}")
            rows.append({"engine": engine, "file": page.name, "lang": lang, "cer_raw": round(raw, 4),
                         "cer_clean": round(cleaned, 4), "seconds": round(seconds, 2), "notes": "; ".join(notes)})

    print("\nAverages (lower CER is better)")
    print(f"{'engine':10} {'lang':4} {'files':>5} {'CER raw':>8} {'CER clean':>9} {'s/page':>7}")
    for engine in args.engines:
        for lang in LANGUAGES:
            mine = [r for r in rows if r["engine"] == engine and r["lang"] == lang]
            if mine:
                print(f"{engine:10} {lang:4} {len(mine):>5} {mean(r['cer_raw'] for r in mine):8.1%} "
                      f"{mean(r['cer_clean'] for r in mine):9.1%} {mean(r['seconds'] for r in mine):7.1f}")

    results = args.folder / "results.csv"
    with results.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {results} and the OCR text in {args.folder / 'ocr_output'}")


if __name__ == "__main__":
    main()
