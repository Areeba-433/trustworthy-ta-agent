import pytest

from app.ingestion.cleaning.common import (clean_text, detect_lang, find_repeated_lines,
                                           garbage_share, is_repeated, title_from_filename)


@pytest.mark.parametrize("raw, expected", [
    ("\ufb01le system", "file system"),                   # 'fi' symbol unfolded
    ("normal-\nization", "normalization"),                # word split across lines joined
    ("one\ntwo\n\nthree", "one two\n\nthree"),            # line wrap joined, paragraph kept
    ("a \u00a0  b", "a b"),                               # extra spaces collapsed
    ("zero\u200bwidth", "zerowidth"),                      # invisible character removed
    ("x\u00b2 + y\u00b2", "x\u00b2 + y\u00b2"),            # maths untouched
    ("Page 3 of 10", ""),                                  # page number dropped
    ("\u2014 \u2022 \u2014", ""),                         # punctuation only dropped
])
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


@pytest.mark.parametrize("raw", ["normal-\nization of\ntables", "\ufb01\u200b x", "Page 2"])
def test_cleaning_twice_changes_nothing(raw):
    once = clean_text(raw)
    assert clean_text(once) == once


@pytest.mark.parametrize("text, lang", [
    ("Normalization removes redundancy", "en"),
    ("3NF ka matlab hai", "en"),
    ("\u062a\u06cc\u0633\u0631\u06cc \u0646\u0627\u0631\u0645\u0644 \u0641\u0627\u0631\u0645", "ur"),
    ("Third normal form \u06cc\u0639\u0646\u06cc \u062a\u06cc\u0633\u0631\u06cc", "mixed"),
])
def test_detect_lang(text, lang):
    assert detect_lang(text) == lang


def test_headers_and_footers_are_found():
    pages = {p: [f"Page {p}", "Database Systems - PUCIT", f"topic {chr(64 + p)} details"] for p in range(1, 6)}
    repeated = find_repeated_lines(pages)
    assert is_repeated("Page 9", repeated)
    assert is_repeated("Database Systems - PUCIT", repeated)
    assert not is_repeated("topic C details", repeated)


def test_garbage_share():
    assert garbage_share("Normal readable text") == 0.0
    assert garbage_share("\u00d9\u00db\u00d8\u00aa\u00db") > 0.5


def test_title_from_filename():
    assert title_from_filename("L4_normalization_final(2).pdf") == "L4 normalization"