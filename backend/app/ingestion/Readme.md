# Ingestion step 1: loading, cleaning and context

Every file a teacher uploads becomes one `ParsedDocument`: a list of cleaned blocks, each with its heading path and location. Four tracks build loaders; the shared pieces make them fit together.

| File | Owner | What it is |
|---|---|---|
| `contract.py` | Minahil | The shapes every loader returns, and `contract_violations()`. Frozen. |
| `registry.py` | Minahil | `@register("pdf", ...)` on your `load()` is how the dispatcher finds you. |
| `dispatcher.py` | Minahil | `dispatch(path, meta)`: PDF pre-check, routing, timing, saving, never crashes. |
| `storage.py` | Minahil | `raw_dir()`, `cache_dir()`, `save_parsed()`, `file_sha256()`. |
| `cleaning/common.py` | Minahil | `clean_text()` (stub until days 1 to 3), `detect_lang()`. |
| `loaders/docs.py` | Areeba | Track 1: digital PDF, DOCX, PPTX |
| `loaders/ocr.py` | Minahil | Track 2: scanned PDF, images, plus `ocr_options()` |
| `loaders/audio.py` | Zuha | Track 3: recordings |
| `loaders/code.py`, `loaders/text.py` | Fariha | Track 4: code, text, Markdown |

All loaders are day-0 stubs: one fake block that passes the contract test. Replace your own file's body; keep the name `load` and its `@register` line. Never copy a shared piece into your file: import it.

## Run it (from `backend/`)

```bash
pip install -r requirements.txt -r requirements/base.txt
pytest tests/ingestion -q                                   # contract + shared pieces
python scripts/inspect_parsed.py path/to/file.pdf           # eyeball the blocks
python scripts/inspect_parsed.py file.pdf --random 10 --blind   # Level 3 check
```

Put your sample files in `tests/ingestion/samples/<track>/` (small ones only; large audio and scans go in the shared drive). The contract test picks them up automatically. Mark slow tests with `@pytest.mark.slow`; CI skips them.

## Rules

- Your libraries go in your own `requirements/<track>.txt`, exact versions only.
- Changing `contract.py` or `cleaning/common.py`: open an issue, one PR by Minahil, all four approve.
- Decisions go in `docs/ingestion-decisions.md`; measured numbers in `docs/ingestion-quality.md`.
