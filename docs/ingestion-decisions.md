# Ingestion decisions log

One line per decision: date, what, who decided. Announce in the group chat **before** acting. The owner of the shared piece decides; everyone it touches is told.

## Decided

| Date | Decision | Who |
|---|---|---|
| 2026-10-08 | Four tracks, split by extraction technique: 1 digital docs (Areeba), 2 scanned text (Minahil), 3 audio (Zuha), 4 code and text (Fariha). Shared pieces: Minahil. | All four |
| 2026-10-08 | Every loader returns the `ParsedDocument` in `backend/app/ingestion/contract.py`; signature `load(path, meta) -> ParsedDocument`; never raises on bad input. Contract changes: one PR by Minahil, approved by all four. | All four |
| 2026-10-08 | No LLM calls during loading and cleaning (only optional audio topic names). Raw output kept under `parsed/<resource_id>/raw/`. | All four |

## Day-0 skeleton choices (proposed by Minahil, confirm at the day-0 meeting)

| Date | Decision | Who |
|---|---|---|
| 2026-10-09 | `ResourceMeta` = `resource_id`, `course_id`, `file_name` (optional, the teacher's original name), `precheck` dict. | Minahil |
| 2026-10-09 | Registry keys are the `SourceType` values. The dispatcher sends `.pdf` to `"pdf"` (Track 1) or `"scanned_pdf"` (Track 2) after the pre-check; other types by extension (`dispatcher.EXTENSIONS`). | Minahil |
| 2026-10-09 | Pre-check field for pictures that may hold text: `precheck["large_image_pages"]: list[int]` (digital pages where pictures cover 30% or more). | Minahil |
| 2026-10-09 | Pre-check v0 thresholds: under 20 non-space characters **and** pictures covering 50%+ = scanned page; over 5% unreadable characters = garbled page; a whole PDF with under 20 characters = no text layer. Any of these sends the file to Track 2. A blank page with no picture is not "scanned". Tune on real files. | Minahil |
| 2026-10-09 | Cleaning names: `clean_text(text, lang=None) -> str`, `detect_lang(text) -> "en" \| "ur" \| "mixed"` (80% / 20% Urdu-script letters). | Minahil |
| 2026-10-09 | `quality.chars_total` = sum of `len(block.text)`; the contract test checks it. | Minahil |
| 2026-10-09 | Paths come from `app/ingestion/storage.py` (`raw_dir()`, `cache_dir()`, `save_parsed()`); the dispatcher saves `parsed.json`, loaders only write `raw/` and the cache. | Minahil |
| 2026-10-09 | `pypdfium2` is pinned once, in `requirements/base.txt`. | Minahil |
| 2026-10-09 | A track whose libraries aren't installed is skipped with a warning; the contract test then fails, naming the requirements file. | Minahil |

## Shared cleaning v1 (proposed by Minahil; needs all four to approve)

| Date | Decision | Who |
|---|---|---|
| 2026-10-09 | `clean_text()` does rules 1 to 4; `finalize_blocks(blocks)` does rules 5 and 7 and renumbers `seq`. Loaders call `clean_text` on every block except tables and code, then `finalize_blocks` once, then compute `chars_total`. | Minahil |
| 2026-10-09 | Rule 1 folds only presentation forms and Latin ligatures (per character NFKC), plus Arabic kaf/yeh/alef maksura to Urdu keheh/ye. Superscripts and subscripts are kept. | Minahil |
| 2026-10-09 | Rule 2 removes control and invisible formatting characters but keeps ZWNJ **and** ZWJ (both used inside Urdu words). | Minahil |
| 2026-10-09 | Rule 3 joins a line-break hyphen only when the next letter is lowercase ("Jean-Paul" keeps its hyphen). | Minahil |
| 2026-10-09 | Rule 4 strips lines that are only a page number of 1 to 3 digits ("12", "Page 12", "12 of 40", "- 12 -", "صفحہ 12"); a 4-digit year is kept. | Minahil |
| 2026-10-09 | Rule 5: a line of up to 120 characters on more than half the pages or slides, and on at least 3, is removed; the page's own number is ignored when comparing. Headings, tables and code are never touched. | Minahil |
| 2026-10-09 | Rule 7 never drops a code block (Track 4 must rebuild files exactly). | Minahil |

## Open

| # | Question | Decides | Suggested answer | By |
|---|---|---|---|---|
| D1 | DOCX has no page numbers. What goes in `loc`? | Minahil (contract) | `page=None`; citations use the heading path ("Lab manual > Section 3.2"). Already how `LOCATION_FIELDS` treats DOCX. | Day 3 |
| D2 | Text in pictures inside DOCX and PPTX, if Docling doesn't OCR them | Minahil (OCR) | Week 2: `ocr_image(image) -> (text, confidence)` in `loaders/ocr.py`; Areeba extracts the pictures. Skip if time is short. | Week 2 |
| D3 | Docling's models in the Docker image | Minahil (Dockerfile) | Uncomment the `docling-tools models download` line once `docs.txt` pins Docling. | Day 2 |
| D4 | Pinned Docling versions | All four | Areeba announces exact versions on day 1. | Day 1 |
| D5 | Wording of teacher-facing messages | Upload UI owner | Use the strings as they are in `dispatcher.py` and each loader. | Day 6 |
| D6 | `extra` keys the chunker may want (`marker`, `rows`, ...) | Chunker owner | `extra` stays private; promote a needed key into the contract instead. | Day 7 |
| D7 | Who builds the upload endpoint and the resources table (status: processing / ready / failed)? | Team | Owner of `api/v1/resources.py`; it calls `is_supported()` before saving and `dispatch()` in a one-job-at-a-time worker. | Day 7 |
