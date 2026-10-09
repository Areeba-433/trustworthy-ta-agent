"""Run the PDF pre-check over many files to tune its thresholds. Owner: Minahil.

Run from backend/:

    python scripts/precheck_report.py path/to/pdfs
    python scripts/precheck_report.py path/to/pdfs --pages        # one line per page too

Tuning workflow: put PDFs you KNOW are digital under a folder named "digital"
and PDFs you know are scanned (or InPage Urdu with a broken text layer) under
a folder named "scanned". The report marks every file the pre-check routes the
other way as WRONG, and lists pages close to a threshold, so you can see how
much room each threshold has before you change it in dispatcher.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion import dispatcher as d  # noqa: E402


def page_ranges(pages: list[int]) -> str:
    """[3, 7, 8, 9] -> "3, 7-9"."""
    if not pages:
        return "-"
    groups, run = [], [pages[0]]
    for n in pages[1:]:
        if n == run[-1] + 1:
            run.append(n)
        else:
            groups.append(run)
            run = [n]
    groups.append(run)
    return ", ".join(str(g[0]) if len(g) == 1 else f"{g[0]}-{g[-1]}" for g in groups)


def expected_route(path: Path) -> str | None:
    parts = {part.lower() for part in path.parts}
    if "digital" in parts:
        return "pdf"
    if "scanned" in parts:
        return "scanned_pdf"
    return None


def near_threshold(page: dict) -> list[str]:
    """Why this page is a close call, if it is one."""
    notes = []
    if page["image_cover"] >= d.SCAN_IMAGE_COVER and d.MIN_TEXT_CHARS / 2 <= page["chars"] <= d.MIN_TEXT_CHARS * 2:
        notes.append(f"chars {page['chars']} near MIN_TEXT_CHARS={d.MIN_TEXT_CHARS}")
    if page["chars"] < d.MIN_TEXT_CHARS and abs(page["image_cover"] - d.SCAN_IMAGE_COVER) <= 0.1:
        notes.append(f"picture cover {page['image_cover']} near SCAN_IMAGE_COVER={d.SCAN_IMAGE_COVER}")
    if page["chars"] >= d.MIN_TEXT_CHARS and d.GARBAGE_SHARE / 2 <= page["garbage"] <= d.GARBAGE_SHARE * 2:
        notes.append(f"garbage {page['garbage']} near GARBAGE_SHARE={d.GARBAGE_SHARE}")
    return notes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="PDF files or folders (searched recursively)")
    parser.add_argument("--pages", action="store_true", help="print every page's numbers")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    files: list[tuple[Path, str]] = []   # (path, name to show)
    for root in args.paths:
        if root.is_dir():
            files += [(p, str(p.relative_to(root))) for p in sorted(root.rglob("*")) if p.suffix.lower() == ".pdf"]
        else:
            files.append((root, root.name))

    print(f"thresholds: MIN_TEXT_CHARS={d.MIN_TEXT_CHARS} SCAN_IMAGE_COVER={d.SCAN_IMAGE_COVER} "
          f"LARGE_IMAGE_COVER={d.LARGE_IMAGE_COVER} GARBAGE_SHARE={d.GARBAGE_SHARE}\n")
    print(f"{'check':6} {'file':40} {'pages':>5} {'route':12} {'reason':19} "
          f"{'scanned':10} {'garbled':10} {'big pictures':12}")
    routes, wrong, close_calls = Counter(), [], []
    for path, shown in files:
        name = shown if len(shown) <= 40 else "..." + shown[-37:]
        try:
            result = d.precheck_pdf(path)
        except Exception as error:   # password-protected or broken: the dispatcher fails these politely
            print(f"{'-':6} {name:40} {'':>5} {'unreadable':12} {str(error)[:60]}")
            routes["unreadable"] += 1
            continue
        routes[result["route"]] += 1
        expected = expected_route(path)
        check = "-" if expected is None else ("ok" if expected == result["route"] else "WRONG")
        if check == "WRONG":
            wrong.append(path)
        print(f"{check:6} {name:40} {result['pages']:>5} {result['route']:12} {result['reason']:19} "
              f"{page_ranges(result['scanned_pages']):10} {page_ranges(result['garbled_pages']):10} "
              f"{page_ranges(result['large_image_pages']):12}")
        for page in result["per_page"]:
            notes = near_threshold(page)
            if notes:
                close_calls.append(f"{path.name} page {page['page']}: " + "; ".join(notes))
            if args.pages:
                print(f"{'':47} p{page['page']:<4} chars={page['chars']:<6} garbage={page['garbage']:<6} "
                      f"picture_cover={page['image_cover']}")

    print(f"\n{len(files)} files: " + ", ".join(f"{route} {n}" for route, n in sorted(routes.items())))
    if wrong:
        print(f"\nRouted the wrong way ({len(wrong)}):")
        for path in wrong:
            print(f"  {path}  (expected {expected_route(path)}; run with --pages to see why)")
    if close_calls:
        print(f"\nClose calls ({len(close_calls)} pages): a small threshold change would flip these")
        for line in close_calls[:30]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
