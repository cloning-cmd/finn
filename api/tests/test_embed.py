"""Hashed TF-IDF retrieval: deterministic, model-free, and ranks the lexically right chunk first."""
from __future__ import annotations

import numpy as np

from api.research import embed

CHUNKS = [
    "We expect operating margin to be in the 20 to 22 percent band for FY27 on constant currency revenue growth of 1 to 2 percent.",
    "The board recommended a final dividend of Rs 22 per share, subject to shareholder approval at the AGM.",
    "Capex for the year was Rs 2,100 crore, mostly on the new plant in Dahej which starts commercial production in Q3.",
    "Attrition came down to 12.9 percent and we added 6,000 employees during the quarter.",
]


def test_hash_vectors_are_stable_and_sized():
    a, b = embed.hash_vector(CHUNKS[0]), embed.hash_vector(CHUNKS[0])
    assert a.shape == (embed.HASH_DIM,) and a.dtype == np.float32
    assert np.array_equal(a, b)
    assert embed.is_current(a.tobytes())
    assert not embed.is_current(b"\x00" * (embed.FASTEMBED_DIM * 4))  # a bge-small vector is stale under the hash backend


def test_tokens_drop_stop_words_and_keep_bigrams():
    t = embed.tokens("The margin guidance for the year")
    assert "the" not in t and "for" not in t
    assert "margin guidance" in t


def test_ranking_prefers_lexical_match():
    mat = embed.stack(embed.embed_texts(CHUNKS))
    sims = embed.similarities(mat, embed.embed_query("operating margin guidance for FY27"))
    assert int(np.argmax(sims)) == 0
    sims = embed.similarities(mat, embed.embed_query("capex and new plant capacity"))
    assert int(np.argmax(sims)) == 2
    sims = embed.similarities(mat, embed.embed_query("dividend per share"))
    assert int(np.argmax(sims)) == 1
