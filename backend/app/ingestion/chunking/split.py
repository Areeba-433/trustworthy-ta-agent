"""split_to_fit(): cut one block that is too long for a chunk, never inside a sentence, a code line or a table row
unless a single one of them is longer than the limit on its own."""
import re

from app.ingestion.chunking.base import TokenCounter

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TABLE_RULE = re.compile(r"^\|?\s*:?-{3,}")          # the |---|---| line under a Markdown table's header row
# (separator, joiner) pairs, tried in order: a smaller one is used only where a bigger one left a piece too long.
_PROSE: list[tuple[str | re.Pattern[str], str]] = [("\n\n", "\n\n"), ("\n", "\n"), (_SENTENCE_END, " "), (" ", " ")]
_LINES: list[tuple[str | re.Pattern[str], str]] = [("\n\n", "\n\n"), ("\n", "\n"), (" ", " ")]


def split_to_fit(text: str, kind: str, limit: int, count: TokenCounter) -> list[str]:
    """Pieces of `text`, each at most `limit` tokens, in their original order."""
    if count(text) <= limit:
        return [text]
    if kind == "table":
        return _split_table(text, limit, count)
    return _split(text, _LINES if kind == "code" else _PROSE, limit, count)


def _split(text: str, separators: list[tuple[str | re.Pattern[str], str]], limit: int,
           count: TokenCounter) -> list[str]:
    if count(text) <= limit:
        return [text]
    for i, (separator, joiner) in enumerate(separators):
        parts = separator.split(text) if isinstance(separator, re.Pattern) else text.split(separator)
        parts = [p for p in parts if p.strip()]
        if len(parts) > 1:
            smaller = [piece for part in parts for piece in _split(part, separators[i + 1:], limit, count)]
            return _pack(smaller, joiner, limit, count)
    return _hard_cut(text, limit, count)


def _pack(parts: list[str], joiner: str, limit: int, count: TokenCounter) -> list[str]:
    """Join neighbouring parts back together while they fit, so pieces are as few as possible."""
    pieces: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{joiner}{part}" if current else part
        if current and count(candidate) > limit:
            pieces.append(current)
            current = part
        else:
            current = candidate
    pieces.append(current)
    return pieces


def _split_table(text: str, limit: int, count: TokenCounter) -> list[str]:
    """Cut between rows; every piece repeats the header, so each one still reads as a table."""
    lines = text.split("\n")
    if len(lines) < 3 or not _TABLE_RULE.match(lines[1]):
        return _split(text, _LINES, limit, count)        # not a Markdown table: cut between lines
    header = lines[:2]
    pieces: list[str] = []
    rows: list[str] = []
    for row in lines[2:]:
        if rows and count("\n".join(header + rows + [row])) > limit:
            pieces.append("\n".join(header + rows))
            rows = []
        rows.append(row)
    pieces.append("\n".join(header + rows))
    return [small for piece in pieces for small in _split(piece, _LINES, limit, count)]


def _hard_cut(text: str, limit: int, count: TokenCounter) -> list[str]:
    """Last resort, for one 'word' longer than the limit (a long URL or encoded data): cut by characters."""
    pieces: list[str] = []
    while text:
        size = len(text)
        while size > 1 and (tokens := count(text[:size])) > limit:
            size = min(size - 1, size * limit // tokens)
        pieces.append(text[:size])
        text = text[size:]
    return pieces