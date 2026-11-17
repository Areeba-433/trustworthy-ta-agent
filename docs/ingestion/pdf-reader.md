# PDF reader: docling-parse's words, pdfium's pages (Minahil, PDF track)

## The problem

Reading PDF pages 50-149 of the OOP book crashed the whole Python process on Windows, with no Python error: the
process just ended (exit codes 0xC0000409, and 0xC0000374, heap corruption). Pages 50-99 crashed on every try.
For our job worker a crash like this would take the worker down, not just one upload.

## How the cause was found (22 Oct 2026)

1. Python's crash reporter (`python -X faulthandler`, built into `try_backend.py`): every crash was inside
   docling-parse, Docling's PDF reader, while it handed finished pages over to Docling (`iter_pages`, `get_task`).
2. Not the number of threads: docling-parse with one thread crashed too.
3. Not the number of pages: pages 100-149 (50 pages) and 883-938 (56) went through. One page set it off: book
   page 94 alone crashed, pages 76 and 77-79 did not.
4. Page 94's pictures are Flate-compressed (like PNG) and stored in CMYK, the four printing inks. The OOP book has
   such pictures on 13 pages: 42, 94, 210, 264, 349, 404, 595, 709, 719, 731, 784, 829, 830. None of them is in
   pages 100-149 or 883-938, which went through with their own pictures.
5. Proof with PDFs made from nothing (`make_picture_pdfs.py`): one page, one small picture, three colour types. Only
   the CMYK one crashes, with docling-parse 7.22.2 (the team's version) and 7.22.4 (the newest, 21 Oct 2026).

## What else was tried

| Option | Result |
|---|---|
| docling-parse 7.22.4 | still crashes |
| Docling's other reader, pypdfium2 | no crash, but its word positions are off on pages that do not start at (0, 0), as the book's start at (54, 55): sentences cut, code mixed into paragraphs, the printer's line ("02 3087 CH01 ... Page 24") read as text |
| OCR | no help: it reads the same page picture, so the crash comes first; and it would change exact characters |

## The fix

`app/ingestion/pdf_backend.py`: docling-parse reads the words, with its drawing switched off; pdfium, the PDF
engine of Chrome, draws the page pictures for the layout and table models. Both measure on the visible page, so
the models' boxes fall on docling-parse's words. Docling 2.134 switches docling-parse's page lines off together
with its drawing, and its reading order uses them, so they are kept on. The reader is part of the cache name.

## What was checked

- The CMYK test PDF, book page 94 and pages 50-99 are read (they crashed before).
  `test_a_cmyk_picture_does_not_end_the_process` (test_converter.py, part 4) keeps it that way.
- The crash reporter prints "access violation" 2 to 4 times in each run of Docling's own reader, even on pages
  100-149, where the run then succeeds: something inside docling-parse goes wrong on other pages too, without
  ending the process. In the runs of our reader, docling-parse's drawing switched off, it printed none.
- Pages 883-938, compared line by line with the result of the day before: the same everywhere but 6 places.
  Better on book pages 888 (its keywords on their own page), 889 (the heading "Microsoft Visual C++") and 912
  (a listing's `//----` line in its place). Page 887: the chapter tab was glued to a paragraph, now taken off by
  `remove_chapter_tabs`. Worse: rows of borderline tables on 922, 936 and 937 (see pdf-table-mode.md).
- Speed on pages 100-149, the two readers taking turns, with Docling's own stage timings:

| Run | Docling's own reader | Ours |
|---|---|---|
| 1 | 101.3 s | 77.7 s |
| 2 | 109.9 s | 86.9 s |

  The layout model takes most of the time (73-105 s of it); reading and drawing the pages 1-8 s. Single runs on
  the laptop vary too much to compare: Docling's own reader took 82 s to 150 s on these pages, ours 78 s to 186 s.
  So only runs taking turns are compared.

## Still open

- Report the bug to docling-parse's developers, with the CMYK test PDF.
- The fix leans on two parts of Docling 2.134's inside (`iter_pages`, `_make_docling_parse_page_content_config`).
  After a Docling upgrade, run test_pdf_backend.py and test_converter.py part 4 (`DOCLING_PDF_TEST=1`).
