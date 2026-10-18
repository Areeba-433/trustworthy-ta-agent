from app.ingestion.messages import format_ranges, hard_to_read, no_text_units


def test_neighbouring_pages_are_grouped():
    assert format_ranges([9, 3, 4, 5, 3]) == "3 to 5, 9"


def test_one_page_reads_as_singular():
    assert hard_to_read([5]).startswith("Page 5 was")
    assert no_text_units("Slides", [4]).startswith("Slide 4 has")