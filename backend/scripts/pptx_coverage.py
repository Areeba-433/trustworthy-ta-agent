"""Where every shape of each deck went, for real decks: numbers and shape types only.

    python -m scripts.pptx_coverage <deck.pptx or folder>

Runs loaders/pptx.extract() (Docling, the slide rules and the coverage audit) with the data folder pointed at a
temporary folder, so nothing is written into the repo. Each deck is named by a short hash; no slide text and no
file name is printed, so the output can be pasted.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

from app.core.config import settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coverage audit of PowerPoint decks (numbers only).")
    parser.add_argument("target", type=Path, help="a .pptx file or a folder of them")
    args = parser.parse_args(argv)
    decks = sorted(args.target.glob("*.pptx")) if args.target.is_dir() else [args.target]
    if not decks or not all(d.is_file() and d.suffix.lower() == ".pptx" for d in decks):
        parser.error("give a .pptx file or a folder holding some")

    from app.ingestion import converter
    from app.ingestion.cleaning.common import title_from_filename
    from app.ingestion.loaders import _pptx_shapes as shapes
    from app.ingestion.loaders.pptx import extract

    before, everything = settings.INGESTION_DATA_DIR, []
    with tempfile.TemporaryDirectory(prefix="pptx_coverage_", ignore_cleanup_errors=True) as tmp:
        settings.INGESTION_DATA_DIR = str(Path(tmp) / "data")
        try:
            if not converter.cache_file("0" * 64, "pptx").resolve().is_relative_to(Path(tmp).resolve()):
                print("STOP: the Docling cache ignores INGESTION_DATA_DIR and would land in the repo. Nothing ran.")
                return 1
            for path in decks:
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                try:
                    found = extract(path, sha, title_from_filename(path.name))
                except Exception as exc:                              # a broken deck: its type only
                    print(f"deck {sha[:12]}: not read ({type(exc).__name__})")
                    continue
                print(f"\ndeck {sha[:12]}: slides {len(found.deck.slides)} | hidden {len(found.deck.hidden_slides)}"
                      f" | blocks {len(found.blocks)}")
                print("\n".join(shapes.summary(found.coverage)))
                everything += found.coverage
        finally:
            settings.INGESTION_DATA_DIR = before
    if len(decks) > 1:
        print(f"\nall {len(decks)} decks")
        print("\n".join(line for line in shapes.summary(everything) if "UNKNOWN" not in line))
    return 0


if __name__ == "__main__":
    sys.exit(main())