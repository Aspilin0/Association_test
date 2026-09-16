"""应用配置：从环境变量读取，提供默认值。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 backend/.env（若存在），不覆盖已有环境变量
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _env_float(key: str, default: float) -> float:
    val = _env(key)
    return float(val) if val else default


def _env_int(key: str, default: int) -> int:
    val = _env(key)
    return int(val) if val else default


class Config:
    def __init__(self) -> None:
        # LLM
        self.llm_provider = _env("LLM_PROVIDER", "deepseek").lower()
        self.llm_api_base = _env("LLM_API_BASE", "https://api.deepseek.com/v1")
        self.llm_api_key = _env("LLM_API_KEY")
        self.llm_model = _env("LLM_MODEL", "deepseek-chat")

        # Embedding
        self.embedding_provider = _env("EMBEDDING_PROVIDER", "char_ngram").lower()
        self.embedding_api_base = _env("EMBEDDING_API_BASE")
        self.embedding_api_key = _env("EMBEDDING_API_KEY")
        self.embedding_model = _env("EMBEDDING_MODEL", "text-embedding-3-small")

        # 综合分权重
        self.w_rt = _env_float("SCORE_W_RT", 0.40)
        self.w_emotion = _env_float("SCORE_W_EMOTION", 0.25)
        self.w_similarity = _env_float("SCORE_W_SIMILARITY", 0.15)
        self.w_connectivity = _env_float("SCORE_W_CONNECTIVITY", 0.20)

        # 相似度内部权重（种子 / 上一词 / 全局质心）
        self.sim_w_seed = _env_float("SIM_W_SEED", 0.35)
        self.sim_w_prev = _env_float("SIM_W_PREV", 0.35)
        self.sim_w_global = _env_float("SIM_W_GLOBAL", 0.30)

        # 反应时基线
        self.baseline_mean_ms = _env_float("BASELINE_MEAN_MS", 1500.0)
        self.baseline_std_ms = _env_float("BASELINE_STD_MS", 500.0)
        self.baseline_alpha = _env_float("BASELINE_ALPHA", 0.2)
        self.rt_back_bonus = _env_float("RT_BACK_BONUS", 0.1)

        # 候选生成
        self.candidate_count = _env_int("CANDIDATE_COUNT", 8)
        self.candidate_generate_n = _env_int("CANDIDATE_GENERATE_N", 16)
        self.temperature = _env_float("TEMPERATURE", 0.9)
        self.dedup_threshold = _env_float("DEDUP_THRESHOLD", 0.85)
        self.back_penalty = _env_float("BACK_PENALTY", 0.5)

        # 会话默认
        self.rounds_per_seed = _env_int("ROUNDS_PER_SEED", 10)

        # CORS
        self.cors_origins = [
            o
            for o in (
                s.strip()
                for s in _env(
                    "CORS_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173",
                ).split(",")
            )
            if o
        ]


config = Config()
