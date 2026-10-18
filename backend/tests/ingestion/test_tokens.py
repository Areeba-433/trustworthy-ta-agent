"""count_tokens(). The first three tests use a stand-in tokenizer: no download, no internet.
The two real-tokenizer tests run only with TOKENIZER_INTEGRATION_TEST=1.
"""
import os
from types import SimpleNamespace

import pytest

from app.ingestion.chunking import tokens

needs_tokenizer = pytest.mark.skipif(
    os.getenv("TOKENIZER_INTEGRATION_TEST") != "1",
    reason="real-tokenizer test: set TOKENIZER_INTEGRATION_TEST=1 (downloads tokenizer.json, about 17 MB, once)")


class _FakeTokenizer:
    """Splits on spaces, one token per word, and remembers how it was called."""
    def __init__(self) -> None:
        self.truncation_off = False
        self.padding_off = False
        self.special_token_flags: list[bool] = []

    def no_truncation(self) -> None:
        self.truncation_off = True

    def no_padding(self) -> None:
        self.padding_off = True

    def encode(self, text: str, add_special_tokens: bool = True) -> SimpleNamespace:
        self.special_token_flags.append(add_special_tokens)
        return SimpleNamespace(ids=list(range(len(text.split()))))


@pytest.fixture
def fresh_cache():
    tokens.get_tokenizer.cache_clear()
    yield
    tokens.get_tokenizer.cache_clear()          # never leave a fake tokenizer behind for the next test


def test_an_empty_text_has_no_tokens_and_loads_nothing(monkeypatch):
    def must_not_load():
        raise AssertionError("the tokenizer was loaded for an empty text")

    monkeypatch.setattr(tokens, "get_tokenizer", must_not_load)
    assert tokens.count_tokens("") == 0


def test_special_tokens_are_not_counted(monkeypatch):
    fake = _FakeTokenizer()
    monkeypatch.setattr(tokens, "get_tokenizer", lambda: fake)
    assert tokens.count_tokens("a linked list") == 3
    assert fake.special_token_flags == [False]


def test_the_pinned_tokenizer_is_loaded_once_and_never_truncates(monkeypatch, fresh_cache):
    fake = _FakeTokenizer()
    calls = []

    class _FakeTokenizerClass:
        @staticmethod
        def from_pretrained(model: str, revision: str) -> _FakeTokenizer:
            calls.append((model, revision))
            return fake

    monkeypatch.setattr(tokens, "Tokenizer", _FakeTokenizerClass)
    assert tokens.get_tokenizer() is tokens.get_tokenizer()
    assert calls == [(tokens.TOKENIZER_MODEL, tokens.TOKENIZER_REVISION)]
    assert fake.truncation_off and fake.padding_off


@needs_tokenizer
def test_a_long_text_is_counted_in_full():
    assert tokens.count_tokens("node " * 10_000) > 8_192         # more than bge-m3's own limit: nothing was cut


@needs_tokenizer
def test_the_embedder_adds_exactly_two_special_tokens():
    text = "A linked list stores each value in its own node."
    with_special_tokens = len(tokens.get_tokenizer().encode(text).ids)
    assert with_special_tokens == tokens.count_tokens(text) + 2