r"""Step 4 of the embeddings guideline: put one checked file's chunks into ChromaDB and read them back.

Run check_docx.py (or ingest_check) on the file first, then from backend:
    python scripts\embed_check.py "Bandit_Levels_0-20_Documentation.docx"
    python scripts\embed_check.py "Bandit_Levels_0-20_Documentation.docx" "how do I find a file by size?"
    python scripts\embed_check.py "Bandit_Levels_0-20_Documentation.docx" --no-index "a question" "another"
Questions after the file name are searched in the test course (step 5); --no-index skips re-embedding the file.
The chunks go into a test course ("manual_check"), so no real course is touched. Prints the times to record.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # backend/, so "app" is found from any folder

from app.core.config import settings
from app.ingestion.contract import ChunkedDocument
from app.rag.embedder import EMBED_MODEL, get_model
from app.rag.retrieve import search
from app.rag.store import collection_for, index_chunks

TEST_COURSE = "manual_check"


def find_chunks(name: str) -> Path:
    runs = sorted(Path(settings.INGESTION_DATA_DIR).glob("*/parsed.json"), key=lambda p: p.stat().st_mtime,
                  reverse=True)
    for parsed in runs:
        if json.loads(parsed.read_text(encoding="utf-8")).get("file_name") == Path(name).name:
            if (parsed.parent / "chunks.json").exists():
                return parsed.parent / "chunks.json"
    sys.exit(f"no chunks.json for {name}: run  python data\\check_docx.py \"{name}\"  first")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    name, questions = args[0], args[1:]
    path = find_chunks(name)
    doc = ChunkedDocument.model_validate_json(path.read_text(encoding="utf-8"))
    doc = doc.model_copy(update={"course_id": TEST_COURSE})

    start = time.perf_counter()
    get_model()
    print(f"model: {EMBED_MODEL}   load {time.perf_counter() - start:.1f} s")
    collection = collection_for(TEST_COURSE)
    if "--no-index" not in sys.argv:
        start = time.perf_counter()
        stored = index_chunks(doc)
        index = time.perf_counter() - start
        mine = collection.get(where={"resource_id": doc.resource_id}, include=["metadatas"])
        with_figure = next((m for m in mine["metadatas"] if m.get("has_figure")), None)
        print(f"file: {name}   chunks.json: {path}")
        print(f"chunks: {len(doc.chunks)} in chunks.json, {stored} stored, {len(mine['ids'])} read back "
              f"({'OK' if len(mine['ids']) == len(doc.chunks) else 'MISMATCH'})")
        print(f"embed + store: {index:.1f} s = {len(doc.chunks) / index:.1f} chunks per second")
        print(f"collection: {collection.name} in {settings.CHROMA_DIR}, {collection.count()} chunks in total")
        if with_figure:
            print("a chunk with a figure, read back:")
            for key, value in with_figure.items():
                print(f"   {key}: {value}")
    for question in questions:
        start = time.perf_counter()
        hits = search(TEST_COURSE, question)
        print(f"\nQ: {question}   ({time.perf_counter() - start:.2f} s)")
        for rank, hit in enumerate(hits, start=1):
            preview = " ".join(hit.text.split())[:110]
            figures = f"  figures: {', '.join(hit.figure_ids)}" if hit.figure_ids else ""
            print(f"  {rank}. {hit.score:.3f}  [{hit.citation}]  {preview}{figures}")


if __name__ == "__main__":
    main()
