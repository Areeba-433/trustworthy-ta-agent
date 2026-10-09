"""Shared cleaning used by Tracks 1 to 3 (never on tables or code). Owner: Minahil.

A change here changes every track's output: announce it to all four, and the
PR must show before and after on every track's samples.

Cleaning never rewrites meaning. It only fixes how text came out of a PDF, a
scan or a transcript. The seven rules from the ingestion plan:

    clean_text(text)          rules 1 to 4, on one block's text
      1. Unicode NFC; fold Arabic presentation forms and Latin ligatures
         ("\ufb01" -> "fi") to normal letters, and Arabic kaf/yeh to the Urdu
         letters. Not NFKC on everything: it would turn x\u00b2 into x2.
      2. Remove control characters and invisible formatting characters
         (zero-width space, BOM, soft hyphen, direction marks), but keep
         ZWNJ (U+200C) and ZWJ (U+200D): Urdu uses them inside words.
      3. Join words hyphenated across line breaks ("normal-\\nization").
      4. Collapse repeated spaces and blank lines; strip lone page numbers.
    finalize_blocks(blocks)   rules 5 and 7, on a whole document
      5. Remove lines repeated on most pages or slides (headers and footers
         the parser missed; every OCR page has them).
      7. Drop blocks that end up empty or are only punctuation (never code);
         renumber seq.
    detect_lang(text)         rule 6, per block

How a loader uses them, in this order:

    text = raw if kind in ("table", "code") else clean_text(raw)
    ... build Block(...) objects ...
    blocks = finalize_blocks(blocks)        # then compute quality.chars_total
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Literal

from app.ingestion.contract import Block

TextLang = Literal["en", "ur", "mixed"]

# ---------------------------------------------------------------------------
# Rule 6: language by script ratio
# ---------------------------------------------------------------------------

# Arabic-script blocks used by Urdu, including presentation forms from PDFs.
_ARABIC_SCRIPT = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                  (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))

UR_SHARE = 0.8   # at least this share of letters in Urdu script -> "ur"
EN_SHARE = 0.2   # at most this share -> "en"; anything between is "mixed"


def _is_urdu_script(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _ARABIC_SCRIPT)


def detect_lang(text: str) -> TextLang:
    """Language by script ratio. Roman Urdu counts as "en" script, which is fine for bge-m3."""
    urdu = latin = 0
    for ch in text:
        if not ch.isalpha():
            continue
        if _is_urdu_script(ch):
            urdu += 1
        else:
            latin += 1
    letters = urdu + latin
    if letters == 0:
        return "en"
    share = urdu / letters
    if share >= UR_SHARE:
        return "ur"
    if share <= EN_SHARE:
        return "en"
    return "mixed"


# ---------------------------------------------------------------------------
# Rule 1: Unicode normalization
# ---------------------------------------------------------------------------

def _needs_compat_fold(ch: str) -> bool:
    code = ord(ch)
    return (0xFB00 <= code <= 0xFB06        # Latin ligatures: ff fi fl ffi ffl ...
            or 0xFB50 <= code <= 0xFDFF     # Arabic presentation forms A
            or 0xFE70 <= code <= 0xFEFF)    # Arabic presentation forms B


# Arabic letters that PDFs and some keyboards emit where Urdu uses its own letter.
# They look the same on screen but are different characters, so a student who
# types the Urdu letter would not match the Arabic one in search.
_URDU_LETTERS = str.maketrans({
    "\u0643": "\u06a9",   # ARABIC KAF -> KEHEH (Urdu kaf)
    "\u064a": "\u06cc",   # ARABIC YEH -> FARSI YEH (Urdu choti ye)
    "\u0649": "\u06cc",   # ALEF MAKSURA -> FARSI YEH
})


def _normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    if any(_needs_compat_fold(ch) for ch in text):
        text = "".join(unicodedata.normalize("NFKC", ch) if _needs_compat_fold(ch) else ch
                       for ch in text)
        text = unicodedata.normalize("NFC", text)   # folded letters may combine with marks
    return text.translate(_URDU_LETTERS)


# ---------------------------------------------------------------------------
# Rule 2: invisible characters
# ---------------------------------------------------------------------------

_KEEP_FORMAT = {"\u200c", "\u200d"}   # ZWNJ and ZWJ: part of Urdu words


def _remove_invisible(text: str) -> str:
    out = []
    for ch in text:
        category = unicodedata.category(ch)
        if ch == "\n":
            out.append(ch)
        elif ch == "\t":
            out.append(" ")
        elif category == "Cc":
            continue                      # control characters (\x00, \x0c form feed, ...)
        elif category == "Cf" and ch not in _KEEP_FORMAT:
            continue                      # zero-width space, BOM, soft hyphen, direction marks
        elif category == "Zs":
            out.append(" ")               # no-break space, thin space, ... -> plain space
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Rule 3: words hyphenated across line breaks
# ---------------------------------------------------------------------------

_LINE_BREAK_HYPHEN = re.compile(r"([^\W\d_])[-\u2010][ ]*\n[ ]*([^\W\d_])")


def _join_hyphenated(text: str) -> str:
    def join(match: re.Match) -> str:
        before, after = match.group(1), match.group(2)
        # "normal-\nization" -> joined; "Jean-\nPaul" or "COVID-\n19" style -> keep the hyphen
        return before + after if after.islower() else f"{before}-{after}"
    return _LINE_BREAK_HYPHEN.sub(join, text)


# ---------------------------------------------------------------------------
# Rule 4: spaces, blank lines, lone page numbers
# ---------------------------------------------------------------------------

# A line that is only a page number: "3", "Page 3", "3 of 20", "- 3 -", or the
# Urdu word for page ("safha") with a number. Up to 3 digits, so a year stays.
_PAGE_NUMBER_LINE = re.compile(
    r"""^\s*(?:
          (?:page|p\.|pg\.?|\u0635\u0641\u062d\u06c1)?\s*\d{1,3}(?:\s*(?:/|of|\u0627\u0632)\s*\d{1,3})?
        | [-\u2013\u2014]\s*\d{1,3}\s*[-\u2013\u2014]
        )\s*$""",
    re.IGNORECASE | re.VERBOSE,
)


def _tidy_spacing(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        line = re.sub(r" {2,}", " ", line).strip()
        if _PAGE_NUMBER_LINE.match(line):
            continue
        lines.append(line)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()   # at most one blank line in a row


def clean_text(text: str, lang: str | None = None) -> str:
    """Rules 1 to 4 on one block's text. Never call it on tables or code.

    `lang` is accepted for the agreed signature; the Urdu-specific steps key
    off the script itself, so passing it is optional.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _normalize_unicode(text)      # rule 1
    text = _remove_invisible(text)       # rule 2
    text = _join_hyphenated(text)        # rule 3
    return _tidy_spacing(text)           # rule 4


# ---------------------------------------------------------------------------
# Rules 5 and 7: whole-document steps
# ---------------------------------------------------------------------------

REPEAT_SHARE = 0.5        # a line on more than half of the pages or slides ...
REPEAT_MIN_UNITS = 3      # ... and on at least 3 of them is a header or footer
REPEAT_MAX_CHARS = 120    # longer lines are content, never furniture

_NEVER_TOUCH = {"table", "code", "heading"}   # headings repeat on purpose ("Example (cont.)")


def _unit(block: Block) -> int | None:
    return block.loc.page if block.loc.page is not None else block.loc.slide


def _signatures(line: str, unit: int) -> set[str]:
    """The line itself, plus one variant per occurrence of the page's own number masked.

    "Lecture 4 | Page 3 of 5" on page 3 and "Lecture 4 | Page 4 of 5" on page 4
    share the variant "lecture 4 | page # of 5", so the footer is found on both.
    Other numbers stay, so "Example 1" on slide 5 and "Example 2" on slide 6
    remain different lines.
    """
    words = " ".join(line.lower().split())
    variants = {words}
    for match in re.finditer(r"\d+", words):
        if int(match.group()) == unit:
            variants.add(words[:match.start()] + "#" + words[match.end():])
    return variants


def repeated_lines(blocks: list[Block], units_total: int | None = None) -> set[str]:
    """Signatures of short lines that appear on most pages or slides (rule 5)."""
    units_with: dict[str, set[int]] = defaultdict(set)
    units_seen: set[int] = set()
    for block in blocks:
        unit = _unit(block)
        if unit is None or block.kind in _NEVER_TOUCH:
            continue
        units_seen.add(unit)
        for line in block.text.split("\n"):
            if line.strip() and len(line) <= REPEAT_MAX_CHARS:
                for signature in _signatures(line, unit):
                    units_with[signature].add(unit)
    total = max(units_total or 0, len(units_seen))
    return {sig for sig, units in units_with.items()
            if len(units) >= REPEAT_MIN_UNITS and len(units) > REPEAT_SHARE * total}


def is_meaningful(text: str) -> bool:
    """Rule 7: at least one letter or digit, in any script."""
    return any(ch.isalnum() for ch in text)


def finalize_blocks(blocks: list[Block], units_total: int | None = None) -> list[Block]:
    """Rules 5 and 7 on a whole document, then seq renumbered 0, 1, 2 ...

    Returns new Block objects; the input list is left unchanged. Documents
    without pages or slides (DOCX, audio, code) skip rule 5.
    """
    furniture = repeated_lines(blocks, units_total)
    kept: list[Block] = []
    for block in blocks:
        text = block.text
        unit = _unit(block)
        if furniture and block.kind not in _NEVER_TOUCH and unit is not None:
            text = "\n".join(line for line in text.split("\n")
                             if not _signatures(line, unit) & furniture).strip()
        if block.kind != "code" and not is_meaningful(text):
            continue                      # code is never dropped: Track 4 must rebuild files exactly
        kept.append(block.model_copy(update={"seq": len(kept), "text": text}, deep=True))
    return kept
