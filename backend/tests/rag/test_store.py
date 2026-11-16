"""ChromaDB store with a fake embedder: runs in seconds, never loads bge-m3."""
import hashlib

import pytest

from app.ingestion.contract import Chunk, ChunkedDocument, Location
from app.rag.store import collection_for, collection_name, delete_resource, get_client, index_chunks, metadata_for


def fake_embed(texts):
    """A small fixed vector per text: the same text always gives the same vector."""
    out = []
    for text in texts:
        digest = hashlib.sha256(text.encode()).digest()
        out.append([b / 255 for b in digest[:8]])
    return out


@pytest.fixture
def client(tmp_path):
    return get_client(str(tmp_path / "chroma"))


def _doc(resource_id="r1", course_id="c1", texts=("First chunk.", "Second chunk."), figures=(None, "fig0")):
    chunks = [Chunk(seq=i, chunk_id=f"{resource_id}:{i}", text=t, heading_path=["Notes", f"Part {i}"],
                    loc=Location(), kinds=["paragraph"] + (["figure"] if f else []), block_seqs=[i],
                    token_count=3, figure_ids=[f"{resource_id}:{f}"] if f else [])
              for i, (t, f) in enumerate(zip(texts, figures))]
    return ChunkedDocument(resource_id=resource_id, course_id=course_id, source_type="docx", title="Notes",
                           chunker="docx-sections/2", chunks=chunks)


def test_each_chunk_is_stored_with_its_text_and_metadata(client):
    assert index_chunks(_doc(), fake_embed, client) == 2
    got = collection_for("c1", client).get(ids=["r1:1"], include=["documents", "metadatas"])
    meta = got["metadatas"][0]
    assert got["documents"] == ["Second chunk."]
    assert (meta["resource_id"], meta["heading"], meta["kinds"]) == ("r1", "Notes > Part 1", "paragraph,figure")
    assert (meta["figure_ids"], meta["has_figure"], meta["chunker"]) == ("r1:fig0", True, "docx-sections/2")
    assert "page" not in meta and "slide" not in meta          # a DOCX has no pages: left out, never empty


def test_metadata_holds_only_text_numbers_and_true_false():
    for chunk in _doc().chunks:
        assert all(isinstance(v, (str, int, float, bool)) for v in metadata_for(chunk, _doc()).values())


def test_indexing_the_same_file_again_replaces_its_chunks(client):
    index_chunks(_doc(), fake_embed, client)
    index_chunks(_doc(texts=("Only one chunk now.",), figures=(None,)), fake_embed, client)
    got = collection_for("c1", client).get(include=["documents"])
    assert got["documents"] == ["Only one chunk now."]           # the old second chunk is gone


def test_courses_never_share_chunks(client):
    index_chunks(_doc(course_id="c1"), fake_embed, client)
    index_chunks(_doc(resource_id="r2", course_id="c2"), fake_embed, client)
    assert collection_for("c1", client).count() == 2
    assert set(collection_for("c2", client).get()["ids"]) == {"r2:0", "r2:1"}


def test_deleting_a_file_removes_only_its_chunks(client):
    index_chunks(_doc(resource_id="r1"), fake_embed, client)
    index_chunks(_doc(resource_id="r2"), fake_embed, client)
    delete_resource("c1", "r1", client)
    assert set(collection_for("c1", client).get()["ids"]) == {"r2:0", "r2:1"}


def test_a_course_uuid_becomes_a_safe_collection_name():
    assert collection_name("3f2a9c1e-5b7d-4e8a-9c21-7d4e5f6a8b90") == "course_3f2a9c1e5b7d4e8a9c217d4e5f6a8b90"
    with pytest.raises(ValueError):
        collection_name("--")
