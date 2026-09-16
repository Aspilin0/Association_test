"""网络构建与在线状态（M1：质心/度数中心度/情绪分布；社区留 M3）。"""
from __future__ import annotations

from collections import Counter

from ..constants import EMOTION_COLORS
from ..embeddings import dot
from ..schemas import NetworkState, Session


def compute_degree(session: Session) -> dict[str, int]:
    deg: dict[str, int] = {}
    for e in session.edges:
        deg[e.frm] = deg.get(e.frm, 0) + 1
        deg[e.to] = deg.get(e.to, 0) + 1
    return deg


def mean_degree(session: Session) -> float:
    if not session.nodes:
        return 0.0
    deg = compute_degree(session)
    total = sum(deg.get(node_id, 0) for node_id in session.nodes)
    return total / len(session.nodes)


def compute_network_state(session: Session, store) -> NetworkState:
    node_count = len(session.nodes)

    centroid = store.centroid_embedding(session)
    centroid_words: list[str] = []
    if centroid is not None and session.nodes:
        scored = sorted(
            session.nodes.values(),
            key=lambda n: -dot(store.embed(n.text), centroid),
        )
        centroid_words = [n.text for n in scored[:5]]

    dist = Counter(n.emotion_type for n in session.nodes.values())
    dominant = dist.most_common(1)[0][0] if dist else "neutral"

    deg = compute_degree(session)
    top_central = sorted(session.nodes.values(), key=lambda n: -deg.get(n.id, 0))
    top_central_words = [n.text for n in top_central[:5]]

    return NetworkState(
        node_count=node_count,
        centroid_words=centroid_words,
        dominant_emotion=dominant,
        emotion_distribution=dict(dist),
        top_central_words=top_central_words,
        communities=[],
    )


def build_network_response(session: Session) -> dict:
    nodes = [
        {
            "id": n.id,
            "text": n.text,
            "emotion_type": n.emotion_type,
            "intensity": n.emotion_intensity,
            "total": n.scores.total,
            "size": round(8 + 16 * n.scores.total, 2),
            "color": EMOTION_COLORS.get(n.emotion_type, "#BDBDBD"),
        }
        for n in session.nodes.values()
    ]
    edges = [
        {"from": e.frm, "to": e.to, "type": e.type, "weight": e.weight}
        for e in session.edges
    ]
    return {"nodes": nodes, "edges": edges}
