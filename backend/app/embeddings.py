"""Embedding 提供方：默认字符 n-gram（离线、确定性），可切换 API。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import httpx

DIM = 512
_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193


def _fnv1a(text: str, mod: int) -> int:
    h = _FNV_OFFSET
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * _FNV_PRIME) & 0xFFFFFFFF
    return h % mod


def _tokens(text: str) -> list[str]:
    t = text.strip()
    if not t:
        return [""]
    toks = list(t)
    for i in range(len(t) - 1):
        toks.append(t[i : i + 2])
    return toks


def normalize(vec: list[float]) -> list[float]:
    n = sum(x * x for x in vec) ** 0.5
    if n == 0:
        return vec
    return [x / n for x in vec]


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def mean_normalized(vecs: list[list[float]]) -> Optional[list[float]]:
    """平均后归一化，作为全局质心；空则返回 None。"""
    if not vecs:
        return None
    dim = len(vecs[0])
    m = [0.0] * dim
    for v in vecs:
        for i in range(dim):
            m[i] += v[i]
    n = len(vecs)
    return normalize([x / n for x in m])


class EmbeddingProvider(ABC):
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """返回已 L2 归一化的向量。"""

    def similarity(self, a: list[float], b: list[float]) -> float:
        return dot(a, b)


class CharNgramEmbedding(EmbeddingProvider):
    name = "char_ngram"

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            v = [0.0] * DIM
            for tok in _tokens(t):
                v[_fnv1a(tok, DIM)] += 1.0
            out.append(normalize(v))
        return out


class OpenAICompatibleEmbedding(EmbeddingProvider):
    name = "api"

    def __init__(self, base: str, key: str, model: str) -> None:
        self.base = base.rstrip("/")
        self.key = key
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{self.base}/embeddings",
                headers={"Authorization": f"Bearer {self.key}"},
                json={"model": self.model, "input": texts},
            )
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [normalize(d["embedding"]) for d in data]


def get_provider(config) -> EmbeddingProvider:
    name = config.embedding_provider
    if name in ("char_ngram", "char", "local"):
        return CharNgramEmbedding()
    if name in ("openai", "api", "openai_compatible"):
        if not config.embedding_api_base:
            raise RuntimeError("EMBEDDING_PROVIDER=api 需要设置 EMBEDDING_API_BASE")
        return OpenAICompatibleEmbedding(
            config.embedding_api_base, config.embedding_api_key, config.embedding_model
        )
    raise RuntimeError(f"未知 embedding provider: {name}")
