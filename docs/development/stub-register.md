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