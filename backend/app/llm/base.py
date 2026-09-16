"""LLM 提供方抽象。"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


def parse_json(text: str) -> Any:
    """尽量从 LLM 输出中解析 JSON（剥离代码围栏、截断容错）。"""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (t.find("["), t.find("{")) if i != -1]
    if not starts:
        raise ValueError(f"无法从 LLM 输出解析 JSON: {text[:200]}")
    start = min(starts)
    for end in range(len(t), start, -1):
        try:
            return json.loads(t[start:end])
        except json.JSONDecodeError:
            continue
    raise ValueError(f"无法从 LLM 输出解析 JSON: {text[:200]}")


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self, messages: list[dict], temperature: float, json_mode: bool = False
    ) -> str:
        """返回助手文本。"""

    async def complete_json(self, messages: list[dict], temperature: float) -> Any:
        text = await self.chat(messages, temperature, json_mode=True)
        return parse_json(text)

    async def complete_text(self, messages: list[dict], temperature: float) -> str:
        return await self.chat(messages, temperature, json_mode=False)
