"""embed_texts(): bge-m3 vectors for chunk texts and questions.

The model is the one our token counter uses (chunking/tokens.py), at the same fixed revision, so a chunk's
token_count is what the model reads and every laptop gets the same vectors. It is downloaded once (about
2.2 GB, kept in the Hugging Face cache) and loaded once per process.
"""
from functools import lru_cache

from app.ingestion.chunking.tokens import TOKENIZER_MODEL, TOKENIZER_REVISION

EMBED_MODEL = TOKENIZER_MODEL           # "BAAI/bge-m3": change it only together with the tokenizer
EMBED_REVISION = TOKENIZER_REVISION
EMBED_DIM = 1024                        # numbers per vector
BATCH_SIZE = 16                         # texts per step: bigger is faster but needs more RAM


@lru_cache(maxsize=1)
def get_model():
    """Load bge-m3 on the CPU (the first call takes a while; later calls reuse it)."""
    from sentence_transformers import SentenceTransformer      # imported here: only code that embeds pays for it
    return SentenceTransformer(EMBED_MODEL, revision=EMBED_REVISION, device="cpu")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """One vector of EMBED_DIM numbers per text, in the same order, each of length 1 (for cosine distance)."""
    if not texts:
        return []
    vectors = get_model().encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=len(texts) > 100)
    return vectors.tolist()
