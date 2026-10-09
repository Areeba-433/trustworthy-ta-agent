# Stub register

A stub is a placeholder function with the right name and output shape that
returns fake data until the real code is ready. Review this table in the
weekly meeting. When you replace a stub, change its status to `real` and
write the PR number.

| Stub | Owner | Used by | Status | Replaced in PR | Notes |
|---|---|---|---|---|---|
| `ingest_resource()` | Member 1 | Member 3 | stub | | upload API calls it |
| `retrieve()` | Member 2 | Member 2, Member 4 | stub | | |
| `answer()` | Member 2 | Member 4 | stub | | chat endpoint calls it |
| `input_guard` / `output_guard` | Member 3 | Member 2 | stub | | pass-through for now |
| `verify` (hallucination, confidence) | Member 1, Member 2 | Member 2 | stub | | |
| `save` node | Member 4 | Member 2 | stub | | chat history |
| Mock chat client (frontend) | Member 4 | Member 3, Member 4 | stub | | `VITE_USE_MOCK=true` |
## Ingestion (day-0 skeleton)

| Stub | Owner | Used by | Status | Replaced in PR | Notes |
|---|---|---|---|---|---|
| `loaders/docs.py` `load()` | Areeba | dispatcher | stub | | Track 1: digital PDF, DOCX, PPTX |
| `loaders/ocr.py` `load()` | Minahil | dispatcher | stub | | Track 2: scanned PDF, images |
| `loaders/ocr.py` `ocr_options()` | Minahil | Areeba | stub | | Docling's default OCR until day 4 |
| `loaders/audio.py` `load()` | Zuha | dispatcher | stub | | Track 3 |
| `loaders/code.py`, `loaders/text.py` `load()` | Fariha | dispatcher | stub | | Track 4 |
| `cleaning/common.py` `clean_text()` | Minahil | Tracks 1 to 3 | real | | v1: rules 1 to 4; `finalize_blocks()` does rules 5 and 7 |
