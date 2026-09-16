"""网络分析（M3）：统计、核心词、情结候选（按情绪簇，无需 networkx）。"""
from __future__ import annotations

from collections import Counter

from ..constants import EMOTION_LABELS
from ..schemas import Session
from .network import compute_degree


def analyze(session: Session) -> dict:
    nodes = list(session.nodes.values())
    words = [n for n in nodes if n.source != "seed"]

    rt_values = [n.reaction_time_ms for n in words if n.reaction_time_ms is not None]
    avg_rt = round(sum(rt_values) / len(rt_values), 0) if rt_values else 0.0
    anomalous = [
        n.text for n in words if n.rt_zscore is not None and n.rt_zscore >= 1.0
    ]

    dist = Counter(n.emotion_type for n in nodes)
    dominant = dist.most_common(1)[0][0] if dist else "neutral"

    deg = compute_degree(session)
    top_central = sorted(nodes, key=lambda n: -deg.get(n.id, 0))
    top_central_words = [n.text for n in top_central[:5]]

    core_words = [n.text for n in sorted(words, key=lambda n: -n.scores.total)[:5]]

    # 情结候选：按情绪簇分组，signal = 簇内词综合分均值
    groups: dict[str, list] = {}
    for n in words:
        groups.setdefault(n.emotion_type, []).append(n)

    complexes = []
    for emotion, members in groups.items():
        signal = sum(n.scores.total for n in members) / len(members)
        core = max(members, key=lambda n: n.scores.total)
        complexes.append(
            {
                "emotion": emotion,
                "emotion_label": EMOTION_LABELS.get(emotion, emotion),
                "core": core.text,
                "nodes": [n.text for n in sorted(members, key=lambda n: -n.scores.total)],
                "signal": round(signal, 3),
            }
        )
    complexes.sort(key=lambda c: -c["signal"])

    return {
        "stats": {
            "node_count": len(nodes),
            "word_count": len(words),
            "edge_count": len(session.edges),
            "avg_rt_ms": avg_rt,
            "anomalous_rt_nodes": anomalous,
            "dominant_emotion": dominant,
            "dominant_emotion_label": EMOTION_LABELS.get(dominant, dominant),
            "emotion_distribution": dict(dist),
        },
        "core_words": core_words,
        "top_central_words": top_central_words,
        "complexes": complexes,
    }
