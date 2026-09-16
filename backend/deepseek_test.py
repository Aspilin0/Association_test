"""用真实 DeepSeek 验证候选多样性与情绪标注。"""
import asyncio
import json

from app import embeddings, llm
from app.config import config
from app.schemas import CreateSessionRequest
from app.services.engine import Engine
from app.services.store import SessionStore


async def main() -> None:
    eng = Engine(config, llm.get_provider(config), SessionStore(embeddings.get_provider(config)))
    r = await eng.create_session(CreateSessionRequest(seed_words=["家"]))
    out = [["create_candidates", r.candidates]]

    for w, rt in [("房子", 1200), ("童年", 2100), ("远行", 900)]:
        s = await eng.submit_word(r.session.id, w, rt, "selected")
        out.append([
            f"submit_{w}",
            {
                "emotion": s.node.emotion_type,
                "intensity": s.node.emotion_intensity,
                "candidates": s.candidates,
            },
        ])

    with open("deepseek_out.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote deepseek_out.json")


if __name__ == "__main__":
    asyncio.run(main())
