"""Shared text cleaning for Tracks 1-3. Never applied to tables or code."""
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal

TextLang = Literal["en", "ur", "mixed"]

_FOLD = re.compile("[\uFB00-\uFB06\uFB50-\uFDFF\uFE70-\uFEFC]")      # "fi"-style ligatures, Urdu display-shape letters
_INVISIBLE = dict.fromkeys(map(ord, "\u00AD\u200B\u200E\u200F\u2060\uFEFF"), None)  # invisible characters to delete
_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")      # control characters
_TRAILING = re.compile(r"[ \t]+\n")                                  # spaces at the end of a line
_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n(?=[a-z])")                # "normal-" + new line + "ization"
_SOFT_BREAK = re.compile(r"(?<!\n)\n(?!\n)")                         # a single line break inside a paragraph
_SPACES = re.compile(r"[ \t\u00A0\u2000-\u200A\u202F\u3000]+")        # runs of any kind of space
_BLANK_LINES = re.compile(r"\n{3,}")                                 # three or more line breaks
_PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.IGNORECASE)   # "3", "Page 3 of 10"
_HAS_WORD = re.compile(r"\w")                                        # at least one letter or digit
_URDU = re.compile("[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFC]")
_LATIN = re.compile("[A-Za-z\u00C0-\u024F]")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s")
_BAD = re.compile("[\uFFFD\uE000-\uF8FF]")                           # "unknown character" symbols
_MOJIBAKE = re.compile("[\u00C0-\u00FF]")                            # what broken Urdu fonts usually turn into


def clean_text(text: str) -> str:
    """Tidy characters and spacing without changing meaning. Returns "" if nothing useful is left."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    text = _FOLD.sub(lambda m: unicodedata.normalize("NFKC", m.group()), text)
    text = text.translate(_INVISIBLE)
    text = _CONTROL.sub("", text)
    text = _TRAILING.sub("\n", text)
    text = _HYPHEN_BREAK.sub("", text)
    text = _SOFT_BREAK.sub(" ", text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n")).strip()
    if _PAGE_NUMBER.match(text) or not _HAS_WORD.search(text):
        return ""
    return text


def detect_lang(text: str) -> TextLang:
    urdu, latin = len(_URDU.findall(text)), len(_LATIN.findall(text))
    if urdu + latin == 0:
        return "en"
    share = urdu / (urdu + latin)
    return "ur" if share >= 0.8 else "en" if share <= 0.2 else "mixed"


def _signature(line: str) -> str:
    return _DIGITS.sub("#", _SPACES.sub(" ", line.strip().lower()))     # "Page 3" and "Page 4" both become "page #"


def find_repeated_lines(lines_by_unit: Mapping[int, Iterable[str]],
                        min_share: float = 0.5, min_units: int = 3) -> set[str]:
    """Lines that appear on more than half the pages: headers and footers."""
    if len(lines_by_unit) < min_units:
        return set()
    counts: Counter[str] = Counter()
    for lines in lines_by_unit.values():
        counts.update({_signature(l) for l in lines if l.strip()})
    limit = min_share * len(lines_by_unit)
    return {sig for sig, n in counts.items() if n > limit and len(sig) <= 120}


def is_repeated(text: str, repeated: set[str]) -> bool:
    return _signature(text) in repeated


def garbage_share(text: str) -> float:
    """How much of the text is broken characters (0 = none, 1 = all)."""
    visible = len(text) - len(_WHITESPACE.findall(text))
    if visible == 0:
        return 0.0
    return (len(_BAD.findall(text)) + len(_MOJIBAKE.findall(text))) / visible


def title_from_filename(file_name: str) -> str:
    """'L4_normalization_final(2).pdf' -> 'L4 normalization'"""
    stem = re.sub(r"\s*\(\d+\)$", "", Path(file_name).stem)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\b(final|copy|new|v\d+)\b", "", stem, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", stem).strip() or "Untitled"