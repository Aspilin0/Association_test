"""DeepSeek（OpenAI 兼容）实现。"""
from __future__ import annotations

import httpx

from .base import LLMProvider


class DeepSeekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self, base: str, key: str, model: str) -> None:
        self.base = base.rstrip("/")
        self.key = key
        self.model = model

    async def chat(self, messages, temperature, json_mode=False) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base}/chat/completions", headers=headers, json=payload
            )
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]
