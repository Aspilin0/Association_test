"""Ollama（本地模型）实现。"""
from __future__ import annotations

import httpx

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base: str = "http://localhost:11434", model: str = "llama3") -> None:
        self.base = base.rstrip("/")
        self.model = model

    async def chat(self, messages, temperature, json_mode=False) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        return data["message"]["content"]
