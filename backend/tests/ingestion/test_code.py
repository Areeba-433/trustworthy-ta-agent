"""Tests for Fariha's track: loaders/code.py and loaders/text.py."""
from pathlib import Path

import pytest

from app.ingestion import messages
from app.ingestion.contract import ResourceMeta
from app.ingestion.dispatcher import ingest_file
from app.ingestion.documents import FileRefused
from app.ingestion.loaders import code as code_loader
from app.ingestion.loaders import text as text_loader
from app.ingestion.precheck import precheck
from app.ingestion.storage import file_sha256

SAMPLES = Path(__file__).parent / "samples" / "code"


def _meta(path: Path) -> ResourceMeta:
    """The same meta the dispatcher would build for this file."""
    return ResourceMeta(resource_id="t1", course_id="c1", file_name=path.name,
                        file_sha256=file_sha256(path), precheck=precheck(path))


def _load_code(name: str):
    return code_loader.load(SAMPLES / name, _meta(SAMPLES / name))


def _load_text(name: str):
    return text_loader.load(SAMPLES / name, _meta(SAMPLES / name))


# ------------------------------------------------------------------ code
@pytest.mark.parametrize("name", ["stack.cpp", "stack.h"])
def test_code_blocks_rebuild_the_original_file(name):
    doc = _load_code(name)
    original = (SAMPLES / name).read_bytes().decode("utf-8")
    assert "".join(b.text for b in doc.blocks) == original


@pytest.mark.parametrize("name", ["stack.cpp", "stack.h"])
def test_code_blocks_have_kind_lang_and_lines(name):
    doc = _load_code(name)
    assert doc.blocks
    for b in doc.blocks:
        assert b.kind == "code"
        assert b.lang == "code"
        assert b.heading_path[0] == name
        assert 1 <= b.loc.line_start <= b.loc.line_end


def test_code_line_numbers_are_continuous():
    doc = _load_code("stack.cpp")
    expected_start = 1
    for b in doc.blocks:
        assert b.loc.line_start == expected_start
        expected_start = b.loc.line_end + 1


def test_code_one_block_per_function_and_class():
    doc = _load_code("stack.cpp")
    paths = [b.heading_path for b in doc.blocks]
    assert ["stack.cpp", "class Stack", "Stack()"] in paths
    assert ["stack.cpp", "class Stack", "push(int x)"] in paths
    assert ["stack.cpp", "class Stack", "pop()"] in paths
    assert ["stack.cpp", "class Stack", "isEmpty()"] in paths
    assert ["stack.cpp", "namespace util", "maxOf(T a, T b)"] in paths
    assert ["stack.cpp", "namespace util", "struct Point"] in paths
    assert ["stack.cpp", "main()"] in paths


def test_class_in_header_gets_class_path():
    doc = _load_code("stack.h")
    assert ["stack.h", "class Stack"] in [b.heading_path for b in doc.blocks]


def test_namespace_qualified_function_says_namespace():
    src = "namespace util { int g(); }\n\nint util::g() { return 1; }\n"
    paths = [s.path for s in code_loader.split_cpp(src)]
    assert ["namespace util", "g()"] in paths


def test_lines_between_two_namespaces_get_no_wrong_namespace():
    src = "namespace a {\nint f() { return 1; }\n}\n\nnamespace b {\nint g() { return 2; }\n}\n"
    segs = code_loader.split_cpp(src)
    assert [s.path for s in segs if s.symbol] == [["namespace a", "f()"], ["namespace b", "g()"]]
    assert all(s.path == [] for s in segs if s.symbol is None)  # "}" of a + "namespace b {"


def test_comment_above_function_stays_with_it():
    doc = _load_code("stack.cpp")
    push = next(b for b in doc.blocks if b.heading_path[-1] == "push(int x)")
    assert push.text.startswith("// Add x on top of the stack.")


def test_includes_go_into_a_header_block():
    doc = _load_code("stack.cpp")
    first = doc.blocks[0]
    assert "#include <iostream>" in first.text
    assert first.heading_path == ["stack.cpp"]


def test_code_is_never_cleaned():
    doc = _load_code("stack.cpp")
    push = next(b for b in doc.blocks if b.heading_path[-1] == "push(int x)")
    lines = push.text.splitlines()
    assert "    if (top >= MAX_SIZE - 1) {" in lines  # indentation kept, line not merged


def test_empty_code_file_fails_politely(tmp_path, data_dir):
    f = tmp_path / "empty.cpp"
    f.write_bytes(b"  \n\n")
    with pytest.raises(FileRefused) as refused:                 # the loader refuses the file...
        code_loader.load(f, _meta(f))
    assert refused.value.reason == messages.NO_TEXT_FILE
    doc = ingest_file(f, "empty_cpp", "c1")                     # ...and the dispatcher fails it politely
    assert doc.blocks == []
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.NO_TEXT_FILE]


def test_broken_code_still_returns_blocks(tmp_path):
    f = tmp_path / "broken.cpp"
    f.write_bytes(b"int main( {\n  return 0\n")
    doc = code_loader.load(f, _meta(f))
    assert "".join(b.text for b in doc.blocks) == "int main( {\n  return 0\n"


def test_windows_line_endings_become_unix_with_the_same_lines(tmp_path):
    original = b"#include <x>\r\n\r\nint f() {\r\n  return 1;\r\n}\r\n"
    f = tmp_path / "win.cpp"
    f.write_bytes(original)
    doc = code_loader.load(f, _meta(f))
    rebuilt = "".join(b.text for b in doc.blocks)
    assert rebuilt == original.decode().replace("\r\n", "\n")      # only the line endings change
    assert "\r" not in rebuilt
    f_block = next(b for b in doc.blocks if b.heading_path == ["win.cpp", "f()"])
    assert (f_block.loc.line_start, f_block.loc.line_end) == (3, 5)  # same line numbers as in the file

def test_functions_returning_a_reference_keep_their_name(tmp_path):
    # Found in testing (oop_operator_overloading.cpp): ostream &operator<<(...) was labelled just "function".
    f = tmp_path / "ops.cpp"
    f.write_bytes(b"#include <iostream>\nstruct T { int h; };\n\n"
                  b"std::ostream &operator<<(std::ostream &out, const T &t)\n{\n    return out << t.h;\n}\n\n"
                  b"int &first(int *a)\n{\n    return a[0];\n}\n\n"
                  b"T &&take(T &t)\n{\n    return static_cast<T &&>(t);\n}\n\n"
                  b"T &T_copy(T &a, const T &b)\n{\n    a = b;\n    return a;\n}\n")
    doc = code_loader.load(f, _meta(f))
    names = [b.heading_path[-1] for b in doc.blocks]
    assert "operator<<(std::ostream &out, const T &t)" in names
    assert "first(int *a)" in names
    assert "take(T &t)" in names                     # && (rvalue reference) too
    assert "T_copy(T &a, const T &b)" in names
    assert "function" not in names

# ------------------------------------------------------------------ text
def test_markdown_headings_become_heading_path():
    doc = _load_text("notes.md")
    para = next(b for b in doc.blocks if b.text.startswith("A stack is a list"))
    assert para.kind == "paragraph"
    assert para.heading_path == ["notes.md", "Lecture 4: Stacks"]

    uses = next(b for b in doc.blocks if b.text.startswith("Undo buttons"))
    assert uses.heading_path == ["notes.md", "Lecture 4: Stacks", "Uses"]


def test_markdown_paragraph_is_cleaned():
    doc = _load_text("notes.md")
    para = next(b for b in doc.blocks if b.text.startswith("A stack is a list"))
    assert "\n" not in para.text  # single line breaks joined by clean_text()


def test_markdown_code_and_table_are_not_cleaned():
    doc = _load_text("notes.md")
    code = next(b for b in doc.blocks if b.kind == "code")
    assert code.text == "```cpp\nStack s;\ns.push(1);\n```"
    assert code.lang == "code"
    table = next(b for b in doc.blocks if b.kind == "table")
    assert table.text.count("\n") == 3


def test_text_blocks_have_line_start():
    for name in ["notes.md", "readme.txt"]:
        doc = _load_text(name)
        assert doc.blocks
        for b in doc.blocks:
            assert b.loc.line_start >= 1
            assert b.heading_path[0] == name


def test_plain_text_splits_on_blank_lines():
    doc = _load_text("readme.txt")
    assert [b.loc.line_start for b in doc.blocks] == [1, 3, 6]
    assert all(b.kind == "paragraph" for b in doc.blocks)
    assert all(b.heading_path == ["readme.txt"] for b in doc.blocks)


def test_empty_text_file_fails_politely(data_dir):
    with pytest.raises(FileRefused) as refused:
        _load_text("empty.txt")
    assert refused.value.reason == messages.NO_TEXT_FILE
    doc = ingest_file(SAMPLES / "empty.txt", "empty_txt", "c1")
    assert doc.blocks == []
    assert doc.quality.status == "failed"
    assert doc.quality.warnings == [messages.NO_TEXT_FILE]


def test_markdown_list_items_stay_on_separate_lines():
    doc = _load_text("notes.md")
    lst = next(b for b in doc.blocks if b.text.startswith("- push"))
    assert lst.text == "- push(x) adds x on top\n- pop() removes the top item"


def test_no_code_block_starts_with_a_blank_line():
    for name in ["stack.cpp", "stack.h"]:
        for b in _load_code(name).blocks:
            assert b.text.split("\n")[0].strip()


# ------------------------------------------------------------------ whole pipeline
@pytest.mark.parametrize("name", ["stack.cpp", "stack.h", "notes.md", "readme.txt"])
def test_samples_go_all_the_way_through_the_dispatcher(name, data_dir):
    doc = ingest_file(SAMPLES / name, "fariha_try", "c1")
    assert doc.quality.status == "ok"
    assert doc.blocks
    assert (data_dir / "fariha_try" / "parsed.json").exists()