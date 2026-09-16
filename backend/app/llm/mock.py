"""离线 Mock 提供方：无 API 也能跑通全流程，仅供开发/测试。"""
from __future__ import annotations

import json
import random

from .base import LLMProvider

# 覆盖多种词类，避免离线 mock 也显得单调
_CANDIDATES = [
    # 具体事物
    "房子", "窗", "门", "灯", "桌子", "院子", "屋顶", "雨", "火",
    # 抽象概念
    "自由", "孤独", "记忆", "命运", "时间", "沉默", "边界", "秘密",
    # 动作（动词）
    "奔跑", "拥抱", "离开", "等待", "坠落", "呼喊", "回头", "寻找",
    # 人物 / 关系
    "母亲", "父亲", "陌生人", "童年",
    # 地点 / 场景
    "远方", "故乡", "车站", "海边",
    # 感官 / 情绪
    "温暖", "寒冷", "疼痛", "甜蜜", "光明", "黑暗",
]

_EMOTION_MAP = [
    ("joy", ["爱", "暖", "笑", "光", "甜", "乐", "喜", "家", "拥抱", "甜蜜", "光明"]),
    ("sadness", ["哭", "泪", "孤", "离", "伤", "痛", "失", "记忆", "沉默", "离开", "等待", "黑暗", "寒冷"]),
    ("fear", ["怕", "恐", "黑", "坠", "死", "陌生人", "坠落", "黑暗"]),
    ("anger", ["怒", "恨", "愤", "火", "呼喊", "冲突"]),
    ("disgust", ["恶", "脏", "呕", "排斥"]),
    ("anticipation", ["望", "期待", "未来", "梦", "寻找", "奔跑", "远方", "海边", "故乡", "自由", "命运"]),
    ("trust", ["信", "依赖", "安心", "忠诚", "父亲", "母亲", "童年"]),
    ("surprise", ["惊", "意外", "突", "回头"]),
]


class MockProvider(LLMProvider):
    name = "mock"

    async def chat(self, messages, temperature, json_mode=False) -> str:
        joined = "".join(m.get("content", "") for m in messages)
        last = messages[-1]["content"] if messages else ""
        if "候选" in joined:
            pool = _CANDIDATES[:]
            random.shuffle(pool)
            return json.dumps(pool[:16], ensure_ascii=False)
        if "情绪" in joined:
            word = last.split("：", 1)[-1].strip()
            for etype, kws in _EMOTION_MAP:
                if any(k in word for k in kws):
                    return json.dumps(
                        {"emotion_type": etype, "emotion_intensity": 0.6},
                        ensure_ascii=False,
                    )
            return json.dumps(
                {"emotion_type": "neutral", "emotion_intensity": 0.0},
                ensure_ascii=False,
            )
        return "{}"
