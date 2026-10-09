"""The parts of scripts/compare_ocr.py that don't need Docling. Owner: Minahil."""

import pytest

from scripts.compare_ocr import cer, edit_distance, find_pairs, normalize_for_cer, reversed_lines


@pytest.mark.parametrize("a,b,distance", [
    ("", "", 0), ("abc", "abc", 0), ("abc", "abd", 1), ("abc", "ab", 1), ("", "abc", 3),
    ("kitten", "sitting", 3), ("کتاب", "كتاب", 1),
])
def test_edit_distance(a, b, distance):
    assert edit_distance(a, b) == distance == edit_distance(b, a)


def test_cer_ignores_layout_but_counts_real_mistakes():
    assert cer("Third normal form", "Third  normal\nform") == 0.0
    assert cer("Third normal form", "Thlrd normal form") == pytest.approx(1 / 17)
    assert cer("", "") == 0.0 and cer("", "noise") == 1.0


def test_normalize_for_cer():
    assert normalize_for_cer("  e\u0301cole \n\n x ") == "école x"


def test_reversed_lines():
    assert reversed_lines("abc\nde") == "cba\ned"


def test_find_pairs(tmp_path, capsys):
    for name in ["en_p1.png", "en_p1.txt", "ur_p2.pdf", "ur_p2.txt", "en_no_truth.jpg", "fr_p3.png", "fr_p3.txt"]:
        (tmp_path / name).write_text("x", encoding="utf-8")
    pairs = find_pairs(tmp_path)
    assert [(page.name, truth.name, lang) for page, truth, lang in pairs] == [
        ("en_p1.png", "en_p1.txt", "en"), ("ur_p2.pdf", "ur_p2.txt", "ur")]
    skipped = capsys.readouterr().out
    assert "en_no_truth.jpg" in skipped and "fr_p3.png" in skipped
