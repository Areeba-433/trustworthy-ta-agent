"""Tests for Fareeha's chunkers: chunking/chunkers/code.py and chunking/chunkers/text.py.

count_tokens() counts one token per word here (the word_tokens fixture), so sizes are easy to read.
"""
from pathlib import Path

import pytest

from app.ingestion.chunking.chunkers import code as code_chunker
from app.ingestion.chunking.registry import get_chunker
from app.ingestion.contract import MAX_CHUNK_TOKENS, ResourceMeta
from app.ingestion.loaders import code as code_loader
from app.ingestion.loaders import text as text_loader
from app.ingestion.pipeline import process
from app.ingestion.precheck import precheck
from app.ingestion.storage import chunks_path, file_sha256

SAMPLES = Path(__file__).parent / "samples" / "code"


def _meta(path: Path) -> ResourceMeta:
    return ResourceMeta(resource_id="t1", course_id="c1", file_name=path.name,
                        file_sha256=file_sha256(path), precheck=precheck(path))


def _code_chunks(path: Path):
    return get_chunker("code")(code_loader.load(path, _meta(path)))


def _text_chunks(path: Path):
    return get_chunker("text")(text_loader.load(path, _meta(path)))


# ------------------------------------------------------------------ code
def test_code_chunker_is_registered_with_its_name(word_tokens):
    chunked = _code_chunks(SAMPLES / "stack.cpp")
    assert chunked.chunker == code_chunker.NAME == "code-units/3"


def test_one_chunk_per_function_and_class(word_tokens):
    paths = [c.heading_path for c in _code_chunks(SAMPLES / "stack.cpp").chunks]
    assert paths == [
        ["stack.cpp", "class Stack", "Stack()"],
        ["stack.cpp", "class Stack", "push(int x)"],
        ["stack.cpp", "class Stack", "pop()"],
        ["stack.cpp", "class Stack", "isEmpty()"],
        ["stack.cpp", "namespace util", "maxOf(T a, T b)"],
        ["stack.cpp", "namespace util", "struct Point"],
        ["stack.cpp", "main()"],
    ]


@pytest.mark.parametrize("name", ["stack.cpp", "stack.h"])
def test_nothing_lost_nothing_repeated(name, word_tokens):
    chunked = _code_chunks(SAMPLES / name)
    assert "".join(c.text for c in chunked.chunks) == (SAMPLES / name).read_bytes().decode("utf-8")


@pytest.mark.parametrize("name", ["stack.cpp", "stack.h"])
def test_code_chunks_follow_the_contract(name, word_tokens):
    for c in _code_chunks(SAMPLES / name).chunks:
        assert c.kinds == ["code"]
        assert c.heading_path[0] == name
        assert 1 <= c.loc.line_start <= c.loc.line_end
        assert 1 <= c.token_count <= MAX_CHUNK_TOKENS


def test_line_numbers_cover_the_file_in_order(word_tokens):
    chunks = _code_chunks(SAMPLES / "stack.cpp").chunks
    assert chunks[0].loc.line_start == 1
    for before, after in zip(chunks, chunks[1:]):
        assert after.loc.line_start == before.loc.line_end + 1


def test_small_opening_glue_joins_the_next_unit(word_tokens):
    chunks = _code_chunks(SAMPLES / "stack.cpp").chunks
    assert chunks[0].text.startswith("#include <iostream>")           # includes go with the first unit
    assert chunks[4].text.startswith("namespace util {")              # "namespace util {" goes with maxOf


def test_closing_glue_joins_the_chunk_it_closes(word_tokens):
    chunks = _code_chunks(SAMPLES / "stack.cpp").chunks
    point = next(c for c in chunks if c.heading_path[-1] == "struct Point")
    assert "}  // namespace util" in point.text
    main = next(c for c in chunks if c.heading_path[-1] == "main()")
    assert main.text.startswith("int main() {")


def test_endif_does_not_become_a_tiny_chunk(word_tokens):
    chunks = _code_chunks(SAMPLES / "stack.h").chunks
    assert [c.heading_path for c in chunks] == [["stack.h", "class Stack"]]
    assert chunks[0].text.rstrip().endswith("#endif")


def test_big_glue_stays_a_chunk_of_its_own(tmp_path, word_tokens):
    globals_ = "".join(f"int value_number_{i} = {i}; // a global counter\n" for i in range(20))
    f = tmp_path / "globals.cpp"
    f.write_bytes((globals_ + "\nint main() {\n  return 0;\n}\n").encode())
    chunks = _code_chunks(f).chunks
    assert [c.heading_path for c in chunks] == [["globals.cpp"], ["globals.cpp", "main()"]]


def test_long_function_is_cut_between_lines_with_exact_lines(tmp_path, word_tokens):
    body = "".join(f"    total = total + {i} * step; // add part {i} of the sum\n" for i in range(80))
    source = "int sum(int step) {\n    int total = 0;\n" + body + "    return total;\n}\n"
    f = tmp_path / "long.cpp"
    f.write_bytes(source.encode())          # write_bytes: the same "\n" on Windows too
    chunks = _code_chunks(f).chunks
    file_lines = source.split("\n")

    assert len(chunks) > 1
    for c in chunks:
        assert c.heading_path == ["long.cpp", "sum(int step)"]
        assert c.token_count <= MAX_CHUNK_TOKENS
        assert c.text.split("\n")[0] == file_lines[c.loc.line_start - 1]      # citation points at the real line
        assert c.text.split("\n")[-1] == file_lines[c.loc.line_end - 1]
    assert chunks[0].loc.line_start == 1
    assert chunks[-1].loc.line_end == len(source.splitlines())


def test_glue_that_does_not_fit_stays_alone(tmp_path, word_tokens, monkeypatch):
    # f() fits the limit on its own, but not together with the includes: the includes stay a chunk of their own,
    # so a whole function is never cut just to make room for glue.
    monkeypatch.setattr(code_chunker, "MAX_CHUNK_TOKENS", 10)       # a tiny limit, just for this test
    f = tmp_path / "x.cpp"
    f.write_bytes(b"#include <vector>\n#include <map>\n#include <set>\n\nint f() {\n  return 1;\n}\n")
    drafts = code_chunker.code_drafts(code_loader.load(f, _meta(f)))
    assert [d.heading_path for d in drafts] == [["x.cpp"], ["x.cpp", "f()"]]

def test_failed_document_is_not_chunked(tmp_path, word_tokens):
    f = tmp_path / "empty.cpp"
    f.write_bytes(b"\n\n")
    with pytest.raises(ValueError):
        code_chunker.code_drafts(code_loader.load(f, _meta(f)))


# ------------------------------------------------------------------ text
def test_markdown_chunks_follow_headings(word_tokens):
    chunks = _text_chunks(SAMPLES / "notes.md").chunks
    assert [c.heading_path for c in chunks] == [
        ["notes.md", "Lecture 4: Stacks"],
        ["notes.md", "Lecture 4: Stacks", "Operations"],
        ["notes.md", "Lecture 4: Stacks", "Uses"],
    ]


def test_markdown_headings_are_not_repeated_as_text(word_tokens):
    for c in _text_chunks(SAMPLES / "notes.md").chunks:
        assert not c.text.startswith("#")
        assert "heading" not in c.kinds


def test_markdown_code_and_table_stay_exact_inside_chunks(word_tokens):
    ops = _text_chunks(SAMPLES / "notes.md").chunks[1]
    assert ops.kinds == ["paragraph", "table", "code"]
    assert "| push      | O(1) |\n| pop       | O(1) |" in ops.text
    assert "```cpp\nStack s;\ns.push(1);\n```" in ops.text
    assert (ops.loc.line_start, ops.loc.line_end) == (8, 19)


def test_plain_text_becomes_one_chunk_with_line_range(word_tokens):
    chunks = _text_chunks(SAMPLES / "readme.txt").chunks
    assert len(chunks) == 1
    assert chunks[0].heading_path == ["readme.txt"]
    assert (chunks[0].loc.line_start, chunks[0].loc.line_end) == (1, 6)


# ------------------------------------------------------------------ whole pipeline
@pytest.mark.parametrize("name", ["stack.cpp", "stack.h", "notes.md", "readme.txt"])
def test_samples_go_all_the_way_to_chunks_json(name, data_dir, word_tokens):
    result = process(SAMPLES / name, "fareeha_chunks", "c1")
    assert result.status == "ok"
    assert result.chunked is not None
    assert chunks_path("fareeha_chunks").exists()


def test_processing_twice_gives_the_same_chunks_json(data_dir, word_tokens):
    process(SAMPLES / "stack.cpp", "again", "c1")
    first = chunks_path("again").read_bytes()
    process(SAMPLES / "stack.cpp", "again", "c1")
    assert chunks_path("again").read_bytes() == first

    

# ------------------------------------------------------------------ special files, end to end
# Each file is generated here (the repo is public: no real course files are committed).
def test_hpp_header_is_chunked_like_code(tmp_path, data_dir, word_tokens):
    f = tmp_path / "shapes.hpp"
    f.write_bytes(b"#pragma once\n\nclass Shape {\npublic:\n    virtual double area() const = 0;\n};\n")
    result = process(f, "shapes", "c1")
    assert result.status == "ok"
    assert [c.heading_path for c in result.chunked.chunks] == [["shapes.hpp", "class Shape"]]


def test_windows_1252_file_is_read_and_chunked(tmp_path, data_dir, word_tokens):
    f = tmp_path / "windows1252.cpp"
    f.write_bytes("// caf\u00e9 \u201cquote\u201d\nint f() { return 1; }\n".encode("cp1252"))   # not UTF-8
    result = process(f, "win1252", "c1")
    assert result.status == "ok"
    assert "caf\u00e9 \u201cquote\u201d" in result.chunked.chunks[0].text      # letters decoded correctly
    assert result.chunked.chunks[0].heading_path == ["windows1252.cpp", "f()"]


def test_broken_code_still_reaches_chunks_json(tmp_path, data_dir, word_tokens):
    f = tmp_path / "broken.cpp"
    f.write_bytes(b"int main( {\n  return 0\nclass X { void f( \n")
    result = process(f, "broken", "c1")
    assert result.status == "ok"
    assert "".join(c.text for c in result.chunked.chunks) == f.read_bytes().decode()
    assert chunks_path("broken").exists()


@pytest.mark.parametrize("name, content", [
    ("blank.cpp", b""),                                   # 0 bytes
    ("blank.md", b"\n\n   \n"),                           # only blank lines
    ("garbage.h", b"\x81\x8d\x8f\x90\x9d\xff\xfe" * 40),  # not text in any encoding we read
])
def test_empty_or_garbage_file_fails_politely_without_chunks(tmp_path, data_dir, word_tokens, name, content):
    f = tmp_path / name
    f.write_bytes(content)
    result = process(f, "bad_file", "c1")
    assert result.status == "failed"
    assert result.chunked is None
    assert result.warnings                                # a message the teacher can read
    assert not chunks_path("bad_file").exists()

    

def test_unclosed_namespace_still_gives_one_chunk_per_function(tmp_path, data_dir, word_tokens):
    # Inside an include guard, "namespace app {" is never closed: Tree-sitter wraps it all in an ERROR node.
    f = tmp_path / "unclosed.cpp"
    f.write_bytes(b"#ifndef APP_H\n#define APP_H\n\nnamespace app {\n\nint add(int a, int b) {\n    return a + b;\n}\n\n"
                  b"class Box {\npublic:\n    int size() const { return 1; }\n};\n\n"
                  b"int main() {\n    return add(1, 2);\n}\n\n#endif\n")
    result = process(f, "unclosed", "c1")
    names = [c.heading_path[-1] for c in result.chunked.chunks]
    assert names == ["add(int a, int b)", "class Box", "main()"]


def test_long_function_with_repeated_lines_keeps_exact_line_numbers(tmp_path, word_tokens):
    # Many identical lines ("    }", "        total += 1;"): line numbers must come from position, not search.
    block = "    if (x > 0) {\n        total += 1;\n    }\n\n"
    source = "int count(int x) {\n    int total = 0;\n" + block * 120 + "    return total;\n}\n"
    f = tmp_path / "repeat.cpp"
    f.write_bytes(source.encode())
    chunks = _code_chunks(f).chunks
    file_lines = source.split("\n")

    assert len(chunks) > 1
    for before, after in zip(chunks, chunks[1:]):
        assert after.loc.line_start > before.loc.line_end                     # in order, no overlap
    for c in chunks:
        piece_lines = [l for l in c.text.split("\n") if l.strip()]
        assert piece_lines[0] == file_lines[c.loc.line_start - 1]
        assert piece_lines[-1] == file_lines[c.loc.line_end - 1]
        assert c.loc.line_end - c.loc.line_start + 1 >= len(piece_lines)
    assert chunks[-1].loc.line_end == len(source.splitlines())

    

def test_closing_glue_after_a_long_function_joins_its_last_piece(tmp_path, word_tokens):
    # The function is cut into pieces; "} // namespace app" and "#endif" must not become tiny chunks.
    body = "".join(f"    total = total + {i} * step; // add part {i} of the sum\n" for i in range(80))
    source = ("#ifndef APP_H\n#define APP_H\n\nnamespace app {\n\nint sum(int step) {\n    int total = 0;\n"
              + body + "    return total;\n}\n\n} // namespace app\n\n#endif\n")
    f = tmp_path / "closing.cpp"
    f.write_bytes(source.encode())
    chunks = _code_chunks(f).chunks
    assert len(chunks) > 1
    assert all(c.heading_path[-1] == "sum(int step)" for c in chunks)       # no glue-only chunk left
    assert "} // namespace app" in chunks[-1].text and "#endif" in chunks[-1].text
    assert chunks[-1].loc.line_end == len(source.splitlines())
    assert all(c.token_count <= MAX_CHUNK_TOKENS for c in chunks)



def test_text_without_blank_lines_keeps_precise_line_numbers(tmp_path, data_dir, word_tokens):
    # 300 lines and not one blank line: the loader cuts it into ~150-word blocks at line boundaries,
    # so each chunk cites a few lines instead of all 300 sharing "lines 1–300".
    f = tmp_path / "log.txt"
    f.write_bytes("".join(f"entry {i} the student ran the stack test and wrote down the result\n"
                          for i in range(1, 301)).encode())
    chunks = process(f, "log", "c1").chunked.chunks
    ranges = [(c.loc.line_start, c.loc.line_end) for c in chunks]
    assert len(ranges) == len(set(ranges)) > 1                              # no two chunks share a range
    assert all(end - start < 60 for start, end in ranges)
    assert ranges[0][0] == 1 and ranges[-1][1] == 300
    for before, after in zip(ranges, ranges[1:]):
        assert after[0] == before[1] + 1                                     # no line lost, none repeated


def test_a_long_markdown_table_is_not_cut(tmp_path, data_dir, word_tokens):
    rows = "".join(f"| op{i} | cost of operation number {i} in the table |\n" for i in range(60))
    f = tmp_path / "table.md"
    f.write_bytes(("# Costs\n\n| Operation | Cost |\n|---|---|\n" + rows).encode())
    blocks = text_loader.load(f, _meta(f)).blocks
    assert [b.kind for b in blocks] == ["heading", "table"]