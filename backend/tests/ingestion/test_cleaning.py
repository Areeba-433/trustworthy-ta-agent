"""Shared cleaning: one before/after test per rule. Owner: Minahil.

If you change a rule in cleaning/common.py, change its test here in the same PR
and show the before and after on every track's samples.
"""

import pytest

from app.ingestion.cleaning.common import (
    clean_text,
    detect_lang,
    finalize_blocks,
    is_meaningful,
    repeated_lines,
)
from app.ingestion.contract import Block, Location

# ---------------------------------------------------------------------------
# Rule 1: Unicode normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("before,after", [
    ("\ufb01rst de\ufb01nition", "first definition"),          # Latin ligature fi
    ("e\u0301cole", "école"),                             # e + combining accent -> é (NFC)
    ("x\u00b2 + y\u00b2", "x\u00b2 + y\u00b2"),                # superscripts survive (no NFKC)
    ("H\u2082O", "H\u2082O"),                                  # subscripts survive
    ("\ufefb", "لا"),                                # lam-alef presentation form -> لا
    ("\ufe91\ufe8e\ufe8f", "باب"),              # presentation forms -> باب
    ("كتاب", "کتاب"),  # Arabic kaf -> Urdu keheh: کتاب
    ("ميں", "میں"),              # Arabic yeh -> Urdu ye: میں
    ("ي\u0654", "ئ"),                                # yeh + hamza mark -> ئ (kept as ئ)
])
def test_rule1_unicode(before, after):
    assert clean_text(before) == after


# ---------------------------------------------------------------------------
# Rule 2: invisible characters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("before,after", [
    ("data\u200bbase", "database"),                   # zero-width space
    ("\ufeffNormalization", "Normalization"),         # BOM at the start
    ("normal\u00adization", "normalization"),         # soft hyphen
    ("page\x0cbreak", "pagebreak"),                   # form feed (control)
    ("\u200fRight to left\u200e", "Right to left"),   # direction marks
    ("one\u00a0two\u2009three", "one two three"),     # no-break and thin spaces
    ("a\tb", "a b"),                                  # tab
])
def test_rule2_invisible_characters(before, after):
    assert clean_text(before) == after


def test_rule2_keeps_zwnj_and_zwj():
    urdu = "می\u200cں ا\u200dہ"
    assert clean_text(urdu) == urdu


# ---------------------------------------------------------------------------
# Rule 3: hyphenation across line breaks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("before,after", [
    ("normal-\nization", "normalization"),
    ("normal- \n  ization", "normalization"),          # stray spaces around the break
    ("de‐\npendency", "dependency"),              # Unicode hyphen
    ("Jean-\nPaul Sartre", "Jean-Paul Sartre"),        # capital after: a real hyphen
    ("well-known terms", "well-known terms"),          # hyphen inside a line: untouched
    ("pages 3-\n5 and 6", "pages 3-\n5 and 6"),        # numbers: untouched
])
def test_rule3_hyphenation(before, after):
    assert clean_text(before) == after


# ---------------------------------------------------------------------------
# Rule 4: spaces, blank lines, lone page numbers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("before,after", [
    ("too    many   spaces", "too many spaces"),
    ("  padded line  ", "padded line"),
    ("first\n\n\n\n\nsecond", "first\n\nsecond"),       # at most one blank line
    ("line one\nline two", "line one\nline two"),       # single line breaks are kept
    ("Joins\n12\nAn inner join", "Joins\nAn inner join"),
    ("Joins\nPage 12\nAn inner join", "Joins\nAn inner join"),
    ("Joins\n12 of 40\nAn inner join", "Joins\nAn inner join"),
    ("Joins\n- 12 -\nAn inner join", "Joins\nAn inner join"),
    ("Joins\nصفحہ 12\nAn inner join", "Joins\nAn inner join"),   # صفحہ 12
    ("In 2024 the course changed.", "In 2024 the course changed."),
    ("2024", "2024"),                                   # a year is not a page number
    ("Step 3", "Step 3"),
])
def test_rule4_spacing_and_page_numbers(before, after):
    assert clean_text(before) == after


def test_rules_together_on_a_pdf_style_paragraph():
    before = "\ufeffThe nor-\nmalization  of a re\ufb02ation\u200b removes\n\n\n\nredundancy.\n7\n"
    assert clean_text(before) == "The normalization of a reflation removes\n\nredundancy."


def test_clean_text_is_idempotent():
    text = "The nor-\nmalization\u00a0of  tables\n\n\n12\nكتاب"
    once = clean_text(text)
    assert clean_text(once) == once


# ---------------------------------------------------------------------------
# Rule 5: lines repeated on most pages
# ---------------------------------------------------------------------------


def block(seq, text, page=None, slide=None, kind="paragraph"):
    return Block(seq=seq, kind=kind, text=text, heading_path=["L4"],
                 loc=Location(page=page, slide=slide))


TOPICS = ["Keys", "Functional dependencies", "1NF", "2NF", "3NF"]


def test_rule5_removes_headers_and_footers_seen_on_most_pages():
    blocks = [block(i, f"CS-204 Databases | Lecture 4 | Page {i + 1} of 5\n{topic} explained.", page=i + 1)
              for i, topic in enumerate(TOPICS)]
    cleaned = finalize_blocks(blocks)
    assert [b.text for b in cleaned] == [f"{topic} explained." for topic in TOPICS]


def test_rule5_keeps_numbered_content_that_differs_per_slide():
    blocks = [block(i, f"Example {i + 1}\nA table with {i + 2} rows.", slide=i + 3) for i in range(5)]
    assert [b.text for b in finalize_blocks(blocks)] == [b.text for b in blocks]


def test_rule5_removes_a_constant_header():
    blocks = [block(i, f"FAST NUCES Lahore\n{topic} explained.", page=i + 1) for i, topic in enumerate(TOPICS)]
    assert [b.text for b in finalize_blocks(blocks)] == [f"{topic} explained." for topic in TOPICS]


def test_rule5_leaves_lines_on_only_a_few_pages():
    blocks = [block(0, "Definition\nA key is unique.", page=1),
              block(1, "Definition\nA superkey contains a key.", page=2),
              block(2, "Examples follow.", page=3),
              block(3, "More examples.", page=4),
              block(4, "Summary.", page=5)]
    assert finalize_blocks(blocks)[0].text == "Definition\nA key is unique."


def test_rule5_never_touches_headings_tables_or_code():
    blocks = []
    for slide in range(1, 5):
        blocks.append(block(len(blocks), "Example (cont.)", slide=slide, kind="heading"))
        blocks.append(block(len(blocks), "| a | b |\n|---|---|\n| 1 | 2 |", slide=slide, kind="table"))
    cleaned = finalize_blocks(blocks)
    assert [b.text for b in cleaned] == [b.text for b in blocks]


def test_rule5_skips_documents_without_pages():
    docx_blocks = [block(i, "Lab manual\nStep text.") for i in range(5)]   # DOCX: no page or slide
    assert repeated_lines(docx_blocks) == set()
    assert [b.text for b in finalize_blocks(docx_blocks)] == ["Lab manual\nStep text."] * 5


# ---------------------------------------------------------------------------
# Rule 6: language per block
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,lang", [
    ("Third normal form removes transitive dependencies.", "en"),
    ("نارملائزیشن ڈیٹا بیس کا ایک اہم تصور ہے", "ur"),
    ("Normalization یعنی ڈیٹا کی ترتیب", "mixed"),
    ("Normalization ka matlab hai data ko organize karna", "en"),   # Roman Urdu = Latin script
    ("123 + 456 = 579", "en"),                                        # no letters at all
])
def test_rule6_detect_lang(text, lang):
    assert detect_lang(text) == lang


# ---------------------------------------------------------------------------
# Rule 7: empty and punctuation-only blocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,keep", [
    ("Normalization", True), ("42", True), ("ڈیٹا", True),
    ("", False), ("   ", False), ("• • •", False), ("----", False), ("\u2026", False),
])
def test_rule7_is_meaningful(text, keep):
    assert is_meaningful(text) is keep


def test_rule7_drops_empty_blocks_and_renumbers_seq():
    blocks = [block(0, "Intro", page=1), block(1, "• • •", page=1), block(2, "Joins", page=2)]
    cleaned = finalize_blocks(blocks)
    assert [(b.seq, b.text) for b in cleaned] == [(0, "Intro"), (1, "Joins")]


def test_rule7_never_drops_code():
    blocks = [block(0, "}", kind="code"), block(1, "int main() {}", kind="code")]
    assert len(finalize_blocks(blocks)) == 2


def test_finalize_blocks_leaves_the_input_unchanged():
    blocks = [block(0, "• • •", page=1), block(1, "Joins", page=2)]
    finalize_blocks(blocks)
    assert [(b.seq, b.text) for b in blocks] == [(0, "• • •"), (1, "Joins")]
