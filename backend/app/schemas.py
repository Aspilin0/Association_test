"""Pydantic 数据模型（与 docs/01-数据模型.md 对应）。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EmotionType = Literal[
    "joy",
    "trust",
    "fear",
    "surprise",
    "sadness",
    "disgust",
    "anger",
    "anticipation",
    "neutral",
]
SourceType = Literal["selected", "free", "seed"]
SubmitSource = Literal["selected", "free"]
EdgeType = Literal["association", "semantic", "emotion"]


class Scores(BaseModel):
    emotion: float = 0.0
    similarity: float = 0.0
    connectivity: float = 0.0
    reaction_time: float = 0.0
    total: float = 0.0


class WordNode(BaseModel):
    id: str
    text: str
    emotion_type: EmotionType = "neutral"
    emotion_intensity: float = 0.0
    scores: Scores = Field(default_factory=Scores)
    reaction_time_ms: Optional[int] = None
    rt_zscore: Optional[float] = None
    order: int = 0
    source: SourceType = "selected"
    is_back: bool = False
    occurrences: int = 1
    seed_of: str = ""
    created_at: str = ""


class Edge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    id: str
    frm: str = Field(alias="from")
    to: str
    type: EdgeType
    weight: float = 1.0


class Options(BaseModel):
    rounds_per_seed: int = 10
    candidate_count: int = 8
    temperature: float = 0.9
    emotion_scheme: str = "plutchik"
    llm_provider: str = "deepseek"


class Baseline(BaseModel):
    mean_rt_ms: float = 1500.0
    std_rt_ms: float = 500.0
    n: int = 0


class Community(BaseModel):
    id: int
    centroid_words: list[str] = Field(default_factory=list)
    dominant_emotion: str = "neutral"


class NetworkState(BaseModel):
    node_count: int = 0
    centroid_words: list[str] = Field(default_factory=list)
    dominant_emotion: str = "neutral"
    emotion_distribution: dict[str, int] = Field(default_factory=dict)
    top_central_words: list[str] = Field(default_factory=list)
    communities: list[Community] = Field(default_factory=list)


class Chain(BaseModel):
    seed: str
    node_ids: list[str] = Field(default_factory=list)


class Session(BaseModel):
    id: str
    seed_words: list[str] = Field(default_factory=list)
    options: Options = Field(default_factory=Options)
    status: str = "running"
    created_at: str = ""
    finished_at: Optional[str] = None
    chains: list[Chain] = Field(default_factory=list)
    nodes: dict[str, WordNode] = Field(default_factory=dict)
    edges: list[Edge] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    baseline: Baseline = Field(default_factory=Baseline)
    network_state: NetworkState = Field(default_factory=NetworkState)


class CandidateMeta(BaseModel):
    text: str
    source: str = "llm"  # llm | back
    is_back: bool = False
    penalty: float = 0.0


# ---- 请求 ----
class CreateSessionRequest(BaseModel):
    seed_words: list[str]
    options: Optional[Options] = None


class SubmitRequest(BaseModel):
    word: str
    reaction_time_ms: int
    source: SubmitSource


# ---- 响应 ----
class SessionStateResponse(BaseModel):
    session: Session
    current_seed: str
    round: int
    rounds_complete: bool = False
    candidates: list[str] = Field(default_factory=list)
    candidates_meta: list[CandidateMeta] = Field(default_factory=list)


class SubmitResponse(BaseModel):
    node: WordNode
    round: int
    current_seed: str
    finished: bool
    rounds_complete: bool = False
    chain: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    candidates_meta: list[CandidateMeta] = Field(default_factory=list)
