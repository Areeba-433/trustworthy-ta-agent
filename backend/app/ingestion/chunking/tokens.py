"""count_tokens(): how long a text is for the embedding model, bge-m3.

Every chunker measures with this one function, so a chunk's token_count means the same thing in every
format and matches what the embedder will read.
"""
from functools import lru_cache

from tokenizers import Tokenizer

TOKENIZER_MODEL = "BAAI/bge-m3"
# A fixed commit of the model repository, not "main": every machine gets the same tokenizer, and once it is
# downloaded it loads offline. Change it only together with the embedding model.
TOKENIZER_REVISION = "be9f7f99731dba86ab44550821489908ef3b4baa"


@lru_cache(maxsize=1)
def get_tokenizer() -> Tokenizer:
    """Download tokenizer.json once (about 17 MB, kept in the Hugging Face cache), then load it from disk."""
    tokenizer = Tokenizer.from_pretrained(TOKENIZER_MODEL, revision=TOKENIZER_REVISION)
    tokenizer.no_truncation()       # count the whole text, however long; never a silent cut-off
    tokenizer.no_padding()
    return tokenizer


def count_tokens(text: str) -> int:
    """Tokens in `text` as bge-m3 splits it, without the two special tokens the embedder adds to every input."""
    if not text:
        return 0
    return len(get_tokenizer().encode(text, add_special_tokens=False).ids)