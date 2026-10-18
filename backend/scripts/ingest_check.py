"""Run one file through ingestion and report what came out.

    python -m scripts.ingest_check path/to/file.pdf

Prints the status, the blocks per kind, the chunk sizes in tokens and the seconds per stage, and saves parsed.json,
chunks.json and a readable preview.md in data/ingestion/check_<file name>/. Exit code 0: ok or degraded; 1: failed.
Every owner measures real files the same way, so the numbers can go straight into the measurement notes.
"""
import argparse
import re
import statistics
import time
from collections import Counter
from pathlib import Path

from app.ingestion.contract import Chunk, ChunkedDocument
from app.ingestion.pipeline import ProcessResult, process
from app.ingestion.precheck import UnsupportedFileType
from app.ingestion.storage import resource_dir, write_text_atomic


def resource_id_for(path: Path) -> str:
    """'Data Structures (3rd ed).pdf' -> 'check_Data-Structures-3rd-ed-': safe as a folder name, same every run."""
    return "check_" + re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem)[:50]


def citation(chunk: Chunk) -> str:
    """How an answer would cite the chunk: 'pp. 4–5', 'slide 3', '12:40–14:05', 'lines 10–24' or its headings."""
    loc = chunk.loc
    if loc.page is not None:
        return f"pp. {loc.page}–{loc.page_end}" if loc.page_end else f"p. {loc.page}"
    if loc.slide is not None:
        return f"slide {loc.slide}"
    if loc.t_start is not None:
        return f"{_clock(loc.t_start)}–{_clock(loc.t_end if loc.t_end is not None else loc.t_start)}"
    if loc.line_start is not None:
        end = loc.line_end if loc.line_end is not None else loc.line_start
        return f"lines {loc.line_start}–{end}" if end != loc.line_start else f"line {loc.line_start}"
    return " > ".join(chunk.heading_path[1:]) or chunk.heading_path[0]     # DOCX: the heading path is the citation


def _clock(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def report(path: Path, result: ProcessResult, seconds: float) -> str:
    parsed, chunked = result.parsed, result.chunked
    kinds = Counter(b.kind for b in parsed.blocks)
    lines = [
        f"{path.name}: {parsed.source_type}, status {result.status}",
        f"warnings: {'; '.join(result.warnings) or 'none'}",
        f"blocks: {len(parsed.blocks)} ({', '.join(f'{kind} {n}' for kind, n in kinds.most_common()) or 'none'})",
    ]
    if chunked:
        sizes = [c.token_count for c in chunked.chunks]
        lines.append(f"chunks: {len(sizes)} ({chunked.chunker}), tokens per chunk: "
                     f"min {min(sizes)}, median {statistics.median(sizes):g}, max {max(sizes)}")
    stages = ", ".join(f"{name.removeprefix('dispatch_')} {secs:.2f}"
                       for name, secs in parsed.quality.seconds_taken.items())
    lines.append(f"seconds: {stages}, total {seconds:.2f}")
    return "\n".join(lines)


def preview(path: Path, chunked: ChunkedDocument) -> str:
    count = len(chunked.chunks)
    parts = [f"# {path.name}: {count} chunk{'' if count == 1 else 's'} ({chunked.chunker})"]
    for c in chunked.chunks:
        parts.append(f"## {c.chunk_id} · {citation(c)} · {c.token_count} tokens\n"
                     f"{' > '.join(c.heading_path)}\n\n{c.text}")
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one file through ingestion and report what came out.")
    parser.add_argument("file", type=Path, help="the file to check, e.g. data/books/dsa.pdf")
    parser.add_argument("--course", default="check", help="course id to use (default: check)")
    args = parser.parse_args(argv)
    if not args.file.is_file():
        parser.error(f"no such file: {args.file}")

    resource_id = resource_id_for(args.file)
    start = time.perf_counter()
    try:
        result = process(args.file, resource_id, args.course)
    except UnsupportedFileType:
        parser.error(f"not a file type we ingest: {args.file.suffix or '(no extension)'}")
    seconds = time.perf_counter() - start

    print(report(args.file, result, seconds))
    folder = resource_dir(resource_id)
    if result.chunked:
        write_text_atomic(folder / "preview.md", preview(args.file, result.chunked))
    print(f"saved in: {folder}")
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())