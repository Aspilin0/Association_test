"""会话内存存储 + embedding 缓存。"""
from __future__ import annotations

import uuid
from typing import Optional

from ..embeddings import EmbeddingProvider, mean_normalized
from ..schemas import Session


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class SessionStore:
    def __init__(self, embeddings: EmbeddingProvider) -> None:
        self.embeddings = embeddings
        self.sessions: dict[str, Session] = {}
        self._embed_cache: dict[str, list[float]] = {}

    # ---- embedding ----
    def embed(self, text: str) -> list[float]:
        if text not in self._embed_cache:
            self._embed_cache[text] = self.embeddings.embed([text])[0]
        return self._embed_cache[text]

    def node_embeddings(self, session: Session) -> list[list[float]]:
        return [self.embed(node.text) for node in session.nodes.values()]

    def centroid_embedding(self, session: Session) -> Optional[list[float]]:
        return mean_normalized(self.node_embeddings(session))

    def text_to_node_id(self, session: Session) -> dict[str, str]:
        return {node.text: node.id for node in session.nodes.values()}

    # ---- session ----
    def put(self, session: Session) -> None:
        self.sessions[session.id] = session

    def get(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)
