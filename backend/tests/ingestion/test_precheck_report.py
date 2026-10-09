"""Helpers of scripts/precheck_report.py. Owner: Minahil."""

from pathlib import Path

import pytest

from scripts.precheck_report import expected_route, near_threshold, page_ranges


@pytest.mark.parametrize("pages,text", [([], "-"), ([4], "4"), ([3, 7, 8, 9], "3, 7-9"), ([1, 2, 3], "1-3")])
def test_page_ranges(pages, text):
    assert page_ranges(pages) == text


def test_expected_route_comes_from_the_folder_name():
    assert expected_route(Path("tune/digital/l4.pdf")) == "pdf"
    assert expected_route(Path("tune/Scanned/notes.pdf")) == "scanned_pdf"
    assert expected_route(Path("tune/l4.pdf")) is None


def test_close_calls_are_reported():
    assert near_threshold({"page": 1, "chars": 25, "garbage": 0.0, "image_cover": 0.9})
    assert near_threshold({"page": 1, "chars": 400, "garbage": 0.06, "image_cover": 0.0})
    assert not near_threshold({"page": 1, "chars": 900, "garbage": 0.0, "image_cover": 0.0})
