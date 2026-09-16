"""LLM 提供方工厂。"""
from __future__ import annotations

import sys

from .base import LLMProvider, parse_json
from .deepseek import DeepSeekProvider
from .mock import MockProvider
from .ollama import OllamaProvider

__all__ = ["LLMProvider", "parse_json", "get_provider"]


def get_provider(config) -> LLMProvider:
    name = config.llm_provider
    if name == "deepseek":
        if not config.llm_api_key:
            print(
                "[warn] LLM_PROVIDER=deepseek 但未设置 LLM_API_KEY，"
                "回退到 mock（离线）",
                file=sys.stderr,
            )
            return MockProvider()
        return DeepSeekProvider(config.llm_api_base, config.llm_api_key, config.llm_model)
    if name == "ollama":
        return OllamaProvider()
    if name == "mock":
        return MockProvider()
    raise RuntimeError(f"未知 LLM provider: {name}")
