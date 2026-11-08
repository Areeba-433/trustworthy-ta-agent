"""Text department (owner: Fariha).

Turns .txt and .md files into blocks:
  * Markdown headings (# ... ######, and underlined === / ---) -> kind="heading"
    and they build the heading_path for everything under them
  * normal text is split on blank lines -> kind="paragraph", cleaned with clean_text()
  * fenced code (``` or ~~~) -> kind="code", lang="code", NOT cleaned
  * Markdown tables (lines starting with |) -> kind="table", NOT cleaned
  * every block has loc.line_start (and line_end), 1-based
"""
from __future__ import annotations

import re
from pathlib import Path

from app.ingestion import messages
from app.ingestion.cleaning.common import clean_text, detect_lang
from app.ingestion.contract import Block, Location, ParsedDocument, QualityReport, ResourceMeta
from app.ingestion.dispatcher import failed_document
from app.ingestion.registry import register
from app.ingestion.storage import Timer

_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_SETEXT_H1 = re.compile(r"^ {0,3}=+\s*$")
_SETEXT_H2 = re.compile(r"^ {0,3}-+\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_TABLE_LINE = re.compile(r"^\s*\|")
_LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_RULE = re.compile(r"^ {0,3}([-*_])(\s*\1){2,}\s*$")

_MARKDOWN_SUFFIXES = {".md", ".markdown"}

# A run of lines with no blank line can be very long (a log, a numbered list, a whole file).
# We cut it at a line boundary every ~150 words, so every block - and so every chunk - keeps
# a precise line range for its citation instead of one range covering hundreds of lines.
_MAX_PARAGRAPH_WORDS = 150

def _decode(raw: bytes) -> str | None:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def split_text(source: str, is_markdown: bool) -> list[dict]:
    """Return raw pieces: {kind, text, depth(for headings), line_start, line_end}.

    Pure function (no contract objects) so it is easy to test.
    """
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    pieces: list[dict] = []
    buf: list[str] = []
    buf_start = 0

    def flush(end_index: int) -> None:
        nonlocal buf
        if any(l.strip() for l in buf):
            is_table = is_markdown and all(_TABLE_LINE.match(l) for l in buf if l.strip())
            pieces.append(
                {
                    "kind": "table" if is_table else "paragraph",
                    "text": "\n".join(buf),
                    "line_start": buf_start + 1,
                    "line_end": end_index,
                }
            )
        buf = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if is_markdown:
            # fenced code block: copy everything until the closing fence
            fence = _FENCE.match(line)
            if fence:
                flush(i)
                marker = fence.group(1)
                j = i + 1
                while j < len(lines) and not lines[j].lstrip().startswith(marker):
                    j += 1
                end = min(j, len(lines) - 1)
                code = "\n".join(lines[i : end + 1])
                pieces.append({"kind": "code", "text": code, "line_start": i + 1, "line_end": end + 1})
                i = end + 1
                buf_start = i
                continue

            # "# Heading"
            atx = _ATX_HEADING.match(line)
            if atx and atx.group(2):
                flush(i)
                pieces.append(
                    {"kind": "heading", "text": atx.group(2), "depth": len(atx.group(1)),
                     "line_start": i + 1, "line_end": i + 1}
                )
                i += 1
                buf_start = i
                continue

            # "Heading" followed by ==== or ---- (only for a single-line paragraph)
            if (
                line.strip()
                and not buf
                and i + 1 < len(lines)
                and (_SETEXT_H1.match(lines[i + 1]) or _SETEXT_H2.match(lines[i + 1]))
                and not _TABLE_LINE.match(line)
            ):
                depth = 1 if _SETEXT_H1.match(lines[i + 1]) else 2
                pieces.append(
                    {"kind": "heading", "text": line.strip(), "depth": depth,
                     "line_start": i + 1, "line_end": i + 2}
                )
                i += 2
                buf_start = i
                continue

        # blank line (or a Markdown rule like --- / ***) ends a paragraph
        if not line.strip() or (is_markdown and not buf and _RULE.match(line)):
            flush(i)
            i += 1
            buf_start = i
            continue

        if not buf:
            buf_start = i
        buf.append(line)
        i += 1
        if (sum(len(l.split()) for l in buf) >= _MAX_PARAGRAPH_WORDS
                and not (is_markdown and _TABLE_LINE.match(line))):   # tables stay whole
            flush(i)
            buf_start = i

    flush(len(lines))
    return pieces


# --------------------------------------------------------------------------
# load(): the department's entry point
# --------------------------------------------------------------------------
_PARSER_VERSION = "2"


@register("text")
def load(path: Path, meta: ResourceMeta) -> ParsedDocument:
    timer = Timer()
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return failed_document(meta, "text", messages.UNREADABLE)

    source = _decode(raw)
    if source is None:
        return failed_document(meta, "text", messages.UNREADABLE)
    if not source.strip():
        return failed_document(meta, "text", messages.NO_TEXT_FILE)

    title = meta.file_name  # e.g. "notes.md"
    is_markdown = Path(meta.file_name).suffix.lower() in _MARKDOWN_SUFFIXES

    with timer("parse"):
        pieces = split_text(source, is_markdown)

    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []  # open headings: (depth, heading text)

    for piece in pieces:
        kind = piece["kind"]

        if kind == "heading":
            text = clean_text(piece["text"])
            if not text:
                continue
            # close headings at the same or deeper level, then open this one
            while stack and stack[-1][0] >= piece["depth"]:
                stack.pop()
            stack.append((piece["depth"], text))
        elif kind in ("code", "table"):
            text = piece["text"]  # tables and code are NEVER cleaned
        elif is_markdown and _LIST_ITEM.match(piece["text"]):
            # a list: clean each line on its own so items are not glued together
            text = "\n".join(c for c in (clean_text(l) for l in piece["text"].split("\n")) if c)
        else:
            text = clean_text(piece["text"])

        if not text.strip():
            continue

        blocks.append(
            Block(
                seq=len(blocks),
                kind=kind,
                text=text,
                heading_path=[title, *(h for _, h in stack)],
                loc=Location(line_start=piece["line_start"], line_end=piece["line_end"]),
                lang="code" if kind == "code" else detect_lang(text),
                extra={"depth": piece["depth"]} if kind == "heading" else {},
            )
        )

    if not blocks:
        return failed_document(meta, "text", messages.NO_TEXT_FILE)

    return ParsedDocument(
        resource_id=meta.resource_id,
        course_id=meta.course_id,
        file_name=meta.file_name,
        file_sha256=meta.file_sha256,
        source_type="text",
        title=title,
        parser="markdown" if is_markdown else "plain-text",
        parser_version=_PARSER_VERSION,
        blocks=blocks,
        quality=QualityReport(
            status="ok",
            units_total=len(source.splitlines()),
            chars_total=sum(len(b.text) for b in blocks),
            seconds_taken=timer.seconds,
        ),
    )