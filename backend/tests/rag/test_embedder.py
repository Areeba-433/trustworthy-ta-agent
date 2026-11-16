"""The real bge-m3 model. Skipped until it is downloaded (step 1 of the embeddings guideline)."""
import math

import pytest

from app.rag.embedder import EMBED_DIM, EMBED_MODEL, EMBED_REVISION, embed_texts


def _model_downloaded() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    return isinstance(try_to_load_from_cache(EMBED_MODEL, "config.json", revision=EMBED_REVISION), str)


needs_model = pytest.mark.skipif(not _model_downloaded(), reason="bge-m3 not downloaded yet (guideline step 1)")


@needs_model
def test_each_text_gets_one_vector_of_length_one():
    vectors = embed_texts(["Binary search needs a sorted array.", "ls -la lists hidden files"])
    assert len(vectors) == 2 and all(len(v) == EMBED_DIM for v in vectors)
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3 for v in vectors)


@needs_model
def test_the_same_text_gives_the_same_vector_and_close_meanings_are_close():
    a, b, c = embed_texts(["How do I list hidden files?", "How do I list hidden files?",
                           "The recipe needs two eggs."])
    assert max(abs(x - y) for x, y in zip(a, b)) < 1e-5
    question = embed_texts(["Which command shows hidden files in a folder?"])[0]
    assert sum(x * y for x, y in zip(question, a)) > sum(x * y for x, y in zip(question, c))


def test_no_texts_need_no_model():
    assert embed_texts([]) == []
