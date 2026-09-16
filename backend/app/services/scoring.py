"""四维评分 + 反应时基线（纯函数，见 docs/02-评分模型.md）。"""
from __future__ import annotations

import math
from typing import Optional

from ..embeddings import dot


def rt_zscore(rt_ms: float, mean: float, std: float) -> float:
    return (rt_ms - mean) / max(std, 100.0)


def rt_score(z: float) -> float:
    """sigmoid 归一化，z=0 → 0.5。"""
    try:
        return 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        return 1.0 if z > 0 else 0.0


def update_baseline(mean: float, std: float, n: int, rt: float, alpha: float):
    """指数移动平均更新基线，返回 (mean, std, n+1)。"""
    var = std * std
    new_mean = alpha * rt + (1.0 - alpha) * mean
    new_var = alpha * (rt - new_mean) ** 2 + (1.0 - alpha) * var
    return new_mean, math.sqrt(new_var), n + 1


def similarity_score(
    emb_word: list[float],
    emb_seed: Optional[list[float]],
    emb_prev: Optional[list[float]],
    emb_global: Optional[list[float]],
    has_prev: bool,
    w_seed: float,
    w_prev: float,
    w_global: float,
) -> float:
    s_seed = dot(emb_word, emb_seed) if emb_seed is not None else 0.0
    s_global = dot(emb_word, emb_global) if emb_global is not None else 0.0
    if has_prev and emb_prev is not None:
        s_prev = dot(emb_word, emb_prev)
        return w_seed * s_seed + w_prev * s_prev + w_global * s_global
    # 无上一词时，其权重并入全局
    return w_seed * s_seed + (w_prev + w_global) * s_global


def connectivity_score(degree: int, occurrences: int) -> float:
    """度数归一化（degree/(degree+1)，单调有界）+ 重复加成。"""
    base = degree / (degree + 1.0)
    return min(1.0, base + 0.2 * (occurrences - 1))


def total_score(
    s_rt: float, s_emotion: float, s_similarity: float, s_connectivity: float, w
) -> float:
    return (
        w.w_rt * s_rt
        + w.w_emotion * s_emotion
        + w.w_similarity * s_similarity
        + w.w_connectivity * s_connectivity
    )
