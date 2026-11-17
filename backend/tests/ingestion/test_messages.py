from app.ingestion.messages import format_ranges, hard_to_read, hidden_units, no_text_units


def test_neighbouring_pages_are_grouped():
    assert format_ranges([9, 3, 4, 5, 3]) == "3 to 5, 9"


def test_one_page_reads_as_singular():
    assert hard_to_read([5]).startswith("Page 5 was")
    assert no_text_units("Slides", [4]).startswith("Slide 4 has")


def test_hidden_slides_are_named_and_the_teacher_is_told_how_to_bring_them_back():
    assert hidden_units("Slides", [5]).startswith("Slide 5 is hidden, so it was left out. Unhide it")
    assert hidden_units("Slides", [9, 5, 6, 7]).startswith("Slides 5 to 7, 9 are hidden, so they were left out.")
