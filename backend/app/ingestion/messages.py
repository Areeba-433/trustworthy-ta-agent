PASSWORD_PROTECTED = "This PDF is password-protected. Please upload an unlocked copy."
TYPE_MISMATCH = "This file's content doesn't match its extension. Please upload the original file."
TOO_LARGE = "This file is larger than the upload limit. Please split it into smaller files."
UNREADABLE = "We couldn't read this file. Check that it opens normally, then upload it again."
NO_TEXT_FILE = "No readable text was found in this file."
NO_TEXT_IMAGE = "This image has no readable text."
IMAGE_HARD_TO_READ = "This image was hard to read; answers from it may be less reliable."
PARTIAL = "Part of this file could not be read, so some content may be missing."
GARBLED = "Some text in this file looks garbled; answers from it may be less reliable."
INTERNAL = "Something went wrong while reading this file. Please try again later."


def format_ranges(nums: list[int]) -> str:
    """[3, 4, 5, 9] -> '3 to 5, 9'"""
    groups: list[list[int]] = []
    for n in sorted(set(nums)):
        if groups and n == groups[-1][-1] + 1:
            groups[-1].append(n)
        else:
            groups.append([n])
    return ", ".join(str(g[0]) if len(g) == 1 else f"{g[0]} to {g[-1]}" for g in groups)


def hard_to_read(pages: list[int]) -> str:
    if len(set(pages)) == 1:
        return f"Page {pages[0]} was hard to read; answers from it may be less reliable."
    return f"Pages {format_ranges(pages)} were hard to read; answers from them may be less reliable."


def no_text_units(unit_name: str, units: list[int]) -> str:
    """unit_name is plural, like "Pages" or "Slides"."""
    if len(set(units)) == 1:
        return f"{unit_name.removesuffix('s')} {units[0]} has no readable text (it may be a picture only)."
    return f"{unit_name} {format_ranges(units)} have no readable text (they may be pictures only)."