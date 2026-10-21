# PDF tables: Docling's ACCURATE table mode (Minahil, PDF track)

## Why this was measured

Docling reads a table in two stages: it finds the words, then its table model (TableFormer) decides where rows and
columns begin and which words go in which cell. The model has two modes, FAST and ACCURATE.

Our own code only rearranges cells Docling made (caption, `\|`, chapter tabs). When the model puts a word or an "x" in
the wrong cell, nothing in the text says which cell was right, so we cannot repair it. A wrong cell is the worst error
for a trustworthy TA: a wrong answer with a citation that looks right (FAST said `push_heap` needs no iterator type;
the book says Random Access).

## What was measured

- Pages: the OOP book, PDF pages 923-937 (Appendix F, its hardest tables: tall rows, cells of several lines, code in
  cells, many empty cells). 16 tables.
- How: `try_table_mode.py`, both modes fresh (no cache), our settings with only the table mode changed, then our own
  table steps. Minahil's laptop, CPU only, 22 Oct 2026.
- Each table that came out differently was checked row by row against the page image.

| | FAST | ACCURATE |
|---|---|---|
| Seconds for the 15 pages, loading the models included | 75.0 | 125.1 |
| Tables the same in both modes | 11 of 16 | 11 of 16 |

The 5 that differ:

| Book page | FAST | ACCURATE |
|---|---|---|
| 925 | right | right, but the chapter tab's words at the end of 3 cells (now taken off by `remove_chapter_tabs`) |
| 929 | "(Sets and multisets only.)" split over two rows | right; tab words in 2 cells (taken off) |
| 932 | section title inside a cell; `inner_product` purposes and arguments mixed | right (one code line on a row of its own) |
| 933 | code and arguments mixed over rows; tab words in cells | arguments right but a stray `iter++)`; the algorithm's code lines one row too low |
| 937 | 5 rows wrong (`push_heap`, `make_heap`, `max_element`/`min_element` merged, `next_permutation`, `adjacent_difference` split) | 1 wrong: the Input "x" of `partial_sort_copy` is on `partial_sort` |

## Decision

**ACCURATE** (`app/ingestion/converter.py`). It fixed most wrong cells and added one.

Cost: about 3 seconds more per table (50 s for 16 tables; an upper bound, since loading the bigger model is included).
The OOP book has at least 37 numbered tables on 68 pages, so a few minutes more per book, once: Docling's result is
cached by the file's hash and our settings. The cache name changed with this setting, so every PDF is read again once.

## Still wrong (known limits)

- Book page 933: the code lines of `partial_sum` sit in the next row's Purpose.
- Book page 937: `partial_sort` gets the Input "x" of `partial_sort_copy`.
- `set_symmetric_ difference x` on page 937 is a typo in the printed book, not an error of ours.

ACCURATE can also add errors (page 937). Check tables again on the next books we get.
