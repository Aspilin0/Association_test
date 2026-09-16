"""用真实 DeepSeek 验证报告生成质量。"""
import asyncio
import json

from app import embeddings, llm
from app.config import config
from app.schemas import CreateSessionRequest, Options
from app.services.engine import Engine
from app.services.store import SessionStore


async def main() -> None:
    eng = Engine(config, llm.get_provider(config), SessionStore(embeddings.get_provider(config)))
    r = await eng.create_session(
        CreateSessionRequest(seed_words=["家", "童年"], options=Options(rounds_per_seed=4))
    )
    sid = r.session.id

    seq = [
        ("房子", 1200), ("母亲", 2300), ("争吵", 1700), ("炊烟", 1500),
        ("秋千", 900), ("告别", 2600), ("自由", 1100), ("孤单", 2000),
    ]
    for w, rt in seq:
        s = await eng.submit_word(sid, w, rt, "selected")
        if s.finished:
            break

    rep = await eng.generate_report(sid)
    with open("report_out.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print("wrote report_out.json")


if __name__ == "__main__":
    asyncio.run(main())
