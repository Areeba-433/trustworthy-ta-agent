# Code and Text Track: Parsing and Chunking Findings

Owner: Fareeha · Branch: `feature/chunk-code` · Date: 2026-11-15

## Scope

| Files | Loader (parsing) | Chunker |
|---|---|---|
| `.cpp`, `.h`, `.hpp` | `app/ingestion/loaders/code.py` (Tree-sitter) | `app/ingestion/chunking/chunkers/code.py` (`code-units/3`) |
| `.txt`, `.md` | `app/ingestion/loaders/text.py` (`parser_version 2`) | shared `chunk_sections()` (`text-sections/1`, unchanged) |

Embeddings were tried locally only and are not part of this PR.

## Files changed

| File | Change |
|---|---|
| `app/ingestion/loaders/code.py` | new: C++ loader |
| `app/ingestion/loaders/text.py` | new: text and Markdown loader |
| `app/ingestion/chunking/chunkers/code.py` | new: one chunk per function or class |
| `tests/ingestion/test_code.py` | new: 26 loader tests |
| `tests/ingestion/test_code_chunking.py` | new: 34 chunker tests |
| `tests/ingestion/samples/code/` | new: 5 small generated samples |
| `requirements.txt` | 2 lines: `tree-sitter==0.25.2`, `tree-sitter-cpp==0.23.4` |
| `docs/ingestion/` | this document and the files it was tested on |

No shared file (`contract.py`, `sections.py`, `split.py`, `base.py`, `tokens.py`, `pipeline.py`) was changed.

## Parsing (loaders)

**Code.** Tree-sitter parses the C++ file and finds every function, class, struct, union, enum and template. Each one becomes a block, with the comment directly above it. The lines in between (`#include`, `using`, globals, `namespace x {`, `}`, `#endif`) become glue blocks, so joining all blocks gives back the file byte for byte. Heading paths look like `stack.cpp > class Stack > push(int x)`. Code is never cleaned. Files with syntax errors (for example a missing `}`) still give one block per function, because the loader also looks inside Tree-sitter's ERROR nodes. UTF-8 is tried first, then Windows-1252.

**Text.** Markdown headings (`#` to `######`, and underlined `===` / `---`) build the heading path. Other text splits on blank lines into paragraphs, cleaned with `clean_text()`; list items are cleaned line by line. Fenced code and tables are kept exactly. A run of lines with no blank line is cut every ~150 words at a line boundary, so every block keeps a precise line range.

Empty or unreadable files return `failed` with a message from `messages.py`, never a crash.

## Chunking strategy

**Code (`code-units/3`): one chunk per function or class.**

1. Every function, class, struct or enum is its own chunk.
2. Small glue (under 64 tokens) is never a chunk of its own: closing glue (`}`, `#endif`) joins the chunk before it; opening glue (`#include`, `namespace x {`) joins the next unit. Big glue (many globals or macros) stays its own chunk.
3. Glue never forces a whole function to be cut; a function that is cut anyway takes the glue into its first or last piece.
4. A unit over 512 tokens is cut between lines by the shared `split_to_fit()`, and each piece keeps its own exact line range.
5. Code is copied exactly: all chunks together rebuild the file.

**Text (`text-sections/1`, shared): by Markdown heading.** Each heading section is chunked on its own and never crosses a heading; `.txt` (no headings) packs paragraphs up to about 384 tokens. Heading text travels in the heading path, not in the chunk text.

All sizes are counted with the bge-m3 tokenizer (`count_tokens()`), never `len()`. No chunk is over 512 tokens.

## Tests

| Test file | Tests | What it proves |
|---|---|---|
| `test_code.py` | 26 | file rebuilds exactly, line numbers without gaps, one block per function or class, comments stay with their function, Windows line endings, broken and empty files |
| `test_code_chunking.py` | 34 | one chunk per function, nothing lost or repeated, 512 limit, exact line ranges for cut pieces, no tiny glue chunks, `.hpp`, Windows-1252, broken, empty and garbage files, unclosed namespace, Markdown headings, tables and code kept exact, text without blank lines, same `chunks.json` on a second run |

Full suite on my laptop, after merging the latest `develop`: `pytest tests/ingestion` → **293 passed, 8 skipped**, no failures.

Mutation checks: with the old placeholder chunker 16 of the first 23 chunking tests failed; every bug-fix test below also fails on the code before its fix.

## Test documents and results

The files are in `docs/ingestion/test-files/code-text/`. All were written for testing; none is real course material. Numbers from `python -m scripts.ingest_check <file>` with the real bge-m3 tokenizer.

| File | What it tests | Status | Blocks | Chunks | Tokens min / median / max | Seconds |
|---|---|---|---|---|---|---|
| `long.cpp` (1129 lines) | long file, unclosed namespace, functions over 512 tokens | ok | 54 | 63 | 24 / 136 / 487 | 2.92 |
| `long_fixed.cpp` | same file with the namespace closed | ok | 54 | 63 | 24 / 136 / 487 | 1.87 |
| `lecture_long.md` (2105 lines) | 124 headings in 4 levels, lists | ok | 663 | 123 | 26 / 310 / 318 | 3.22 |
| `lab_long.txt` (7093 lines) | no headings, 420 lines with no blank line | ok | 1167 | 355 | 102 / 335 / 349 | 5.79 |

`long.cpp` and `long_fixed.cpp` give the same chunks: the missing `}` does not change how the file is cut.

Empty, unreadable, `.hpp`, Windows-1252 and broken files are covered by generated files inside `test_code_chunking.py`.

## Bugs found by the real files (all fixed)

| Found by | Problem | Fix |
|---|---|---|
| `long.cpp` | A missing `}` made Tree-sitter wrap the file in one ERROR node, so the whole file became one block | the loader looks inside ERROR nodes |
| `long.cpp` | Cut pieces of long functions got wrong line numbers (a line such as `    }` was found by searching its text) | line numbers come from position, not search |
| `long.cpp` | `} // namespace` and `#endif` after a long function became tiny chunks of 7 and 13 tokens | glue joins a function that is cut anyway (`code-units/3`) |
| `lab_long.txt` | 420 lines with no blank line became one block, so 53 chunks all cited "lines 6675–7094" | long blank-line-free text is cut every ~150 words; each chunk now cites about 5 lines (`parser_version 2`) |

## Known limitations

- Only C++ is supported as code, because `precheck.py` maps only `.cpp`, `.h`, `.hpp` to the code loader.
- A `.txt` chunk can hold the end of one topic and the start of the next, because plain text has no headings to stop at.
- Identical paragraphs give identical chunks; duplicates are not removed.
- A Markdown table over 512 tokens is split by the shared splitter and its pieces share the table's line range.

## Decisions to confirm

- The title of code and text documents is the full file name (`stack.cpp`), not `title_from_filename()`, which would turn both `stack.cpp` and `stack.h` into `stack`.
- In Markdown lists, `clean_text()` runs on each line separately so items do not merge.

## How to reproduce

```powershell
cd backend
pytest tests/ingestion/test_code.py tests/ingestion/test_code_chunking.py -v
python -m scripts.ingest_check ../docs/ingestion/test-files/code-text/long.cpp
```
The readable chunks are written to `data/ingestion/check_<name>/preview.md`.