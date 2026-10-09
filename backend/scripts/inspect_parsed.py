"""Print a readable view of what ingestion makes of a file. Owner: Minahil.

Run from backend/:

    python scripts/inspect_parsed.py tests/ingestion/samples/day0/stacks.pptx
    python scripts/inspect_parsed.py lecture4.pdf --random 10 --blind     # Level 3 check
    python scripts/inspect_parsed.py parsed/<resource_id>/parsed.json     # a saved result

--random N shows N random blocks; --blind hides the file name so you judge the
block from its heading path and text alone (can you tell the topic and where
it's from?). Nothing is saved to parsed/.
"""

from __future__ import annotations

import argparse
import os
import random
import re
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion.contract import Block, ParsedDocument, ResourceMeta, contract_violations  # noqa: E402
from app.ingestion.dispatcher import dispatch  # noqa: E402


def where(block: Block) -> str:
    loc = block.loc
    if loc.page is not None:
        return f"page {loc.page}"
    if loc.slide is not None:
        return f"slide {loc.slide}"
    if loc.line_start is not None:
        return f"lines {loc.line_start}-{loc.line_end}"
    if loc.t_start is not None:
        return f"{loc.t_start:.0f}s-{loc.t_end:.0f}s"
    return "no location"


def show(doc: ParsedDocument, blocks: list[Block], blind: bool, width: int) -> None:
    q = doc.quality
    if not blind:
        print(f"file      {doc.file_name}  ({doc.source_type}, {doc.parser} {doc.parser_version})")
    print(f"title     {doc.title}")
    print(f"quality   {q.status}  units={q.units_total}  ocr_units={q.units_ocr}  chars={q.chars_total}"
          + (f"  avg_conf={q.avg_confidence:.2f}" if q.avg_confidence is not None else ""))
    print(f"seconds   {q.seconds_taken}")
    for warning in q.warnings:
        print(f"warning   {warning}")
    problems = contract_violations(doc)
    print("contract  " + ("OK" if not problems else f"{len(problems)} problem(s): " + "; ".join(problems[:5])))
    print(f"blocks    showing {len(blocks)} of {len(doc.blocks)}")
    for b in blocks:
        conf = f" conf={b.confidence:.2f}" if b.confidence is not None else ""
        print("\n" + "-" * width)
        print(f"#{b.seq} {b.kind} | {where(b)} | lang={b.lang}{conf}")
        print("path: " + " > ".join(b.heading_path))
        body = b.text if b.kind in ("code", "table") else textwrap.fill(b.text, width)
        print(body[:1500] + (" [...]" if len(body) > 1500 else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    parser.add_argument("--random", type=int, metavar="N", help="show N random blocks")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--blind", action="store_true", help="hide the file name (Level 3)")
    parser.add_argument("--width", type=int, default=100)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Urdu on a Windows console

    if args.file.name == "parsed.json":
        doc = ParsedDocument.model_validate_json(args.file.read_text(encoding="utf-8"))
    else:
        resource_id = "inspect-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", args.file.stem)
        doc = dispatch(args.file, ResourceMeta(resource_id=resource_id, course_id="inspect",
                                               file_name=args.file.name), save=False)
    blocks = doc.blocks
    if args.random:
        blocks = sorted(random.Random(args.seed).sample(blocks, min(args.random, len(blocks))),
                        key=lambda b: b.seq)
    show(doc, blocks, args.blind, args.width)


if __name__ == "__main__":
    main()
