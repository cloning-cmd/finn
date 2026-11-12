"""Chunk embeddings with two backends, chosen by `EMBED_BACKEND`:

  hash      (default) hashed TF vectors: unigrams + bigrams, stop words removed, sublinear TF, feature hashing to
            1024 dims with a stable sign hash. IDF is applied at query time from the ticker's own chunk matrix, so
            the stored vector is just the term-frequency side. No model, no download, ~0 MB RSS; retrieval is
            lexical (BM25-like), which is what the quote verifier and the promise matcher need.
  fastembed BAAI/bge-small-en-v1.5 via ONNX (384 dims). Better semantic recall, but the model load + a batch of
            embeddings costs ~430 MB RSS on top of the API process, which OOM-kills a 512 MiB Render instance.

Vectors are stored as float32 bytes; the backend is recognised from the vector length, so chunks written by the
other backend are re-embedded lazily the first time they are searched (`api.research.docs.search_chunks`).
"""
from __future__ import annotations

import math
import re
import zlib
from typing import Iterable

import numpy as np

from api.config import settings

HASH_DIM = 1024
FASTEMBED_DIM = 384
TOKEN = re.compile(r"[a-z][a-z0-9&'\-]*|\d+(?:\.\d+)?%?")
STOP = set("""a an and are as at be been but by for from has have had he her his if in into is it its of on or our
that the their there these they this to was we were which will with would you your not no can could should may
might also than then over under per about across after before more most such very said say says""".split())

_fastembed = None


def backend() -> str:
    b = (settings.embed_backend or "hash").lower()
    return "fastembed" if b == "fastembed" else "hash"


def dim(b: str | None = None) -> int:
    return FASTEMBED_DIM if (b or backend()) == "fastembed" else HASH_DIM


# ----------------------------------------------------------------------------- hash backend (pure numpy)


def tokens(text: str) -> list[str]:
    words = [w for w in TOKEN.findall(text.lower()) if w not in STOP and len(w) > 1]
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


def _slot(term: str) -> tuple[int, float]:
    h = zlib.crc32(term.encode("utf-8"))
    return h % HASH_DIM, 1.0 if (h >> 31) & 1 else -1.0


def hash_vector(text: str) -> np.ndarray:
    v = np.zeros(HASH_DIM, dtype=np.float32)
    counts: dict[str, int] = {}
    for t in tokens(text):
        counts[t] = counts.get(t, 0) + 1
    for term, n in counts.items():
        i, sign = _slot(term)
        v[i] += sign * (1.0 + math.log(n))
    return v


def idf_weights(mat: np.ndarray) -> np.ndarray:
    """Per-dimension IDF from the matrix being searched (n×HASH_DIM)."""
    n = mat.shape[0]
    df = np.count_nonzero(mat, axis=0)
    return np.log((n + 1.0) / (df + 1.0)) + 1.0


# ----------------------------------------------------------------------------- fastembed backend (opt-in)


def fastembed_model():
    global _fastembed
    if _fastembed is None:
        from fastembed import TextEmbedding
        _fastembed = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _fastembed


# ----------------------------------------------------------------------------- public


def embed_texts(texts: list[str]) -> list[bytes]:
    if not texts:
        return []
    if backend() == "fastembed":
        vecs = list(fastembed_model().embed(texts, batch_size=16))
        return [np.asarray(v, dtype=np.float32).tobytes() for v in vecs]
    return [hash_vector(t).tobytes() for t in texts]


def embed_query(text: str) -> np.ndarray:
    if backend() == "fastembed":
        return np.asarray(list(fastembed_model().query_embed(text))[0], dtype=np.float32)
    return hash_vector(text)


def is_current(blob: bytes | None) -> bool:
    return blob is not None and len(blob) == dim() * 4


def similarities(mat: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Cosine similarity of every row against q; hash backend applies IDF from `mat` first."""
    if backend() != "fastembed":
        w = idf_weights(mat)
        mat = mat * w
        q = q * w
    return mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-9)


def stack(blobs: Iterable[bytes]) -> np.ndarray:
    return np.stack([np.frombuffer(b, dtype=np.float32) for b in blobs])
