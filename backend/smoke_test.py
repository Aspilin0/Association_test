"""进程内冒烟测试：验证 建会话 → 提交 → 网络 全链路。"""
import asyncio

from app import embeddings as emb_mod
from app import llm as llm_mod
from app.config import Config
from app.schemas import CreateSessionRequest
from app.services.engine import Engine
from app.services.store import SessionStore


async def main() -> None:
    config = Config()
    config.llm_provider = "mock"
    config.embedding_provider = "char_ngram"

    llm = llm_mod.get_provider(config)
    emb = emb_mod.get_provider(config)
    store = SessionStore(emb)
    engine = Engine(config, llm, store)

    r = await engine.create_session(CreateSessionRequest(seed_words=["家", "母亲"]))
    print(f"[create] seed={r.current_seed} round={r.round} cands={r.candidates}")

    sid = r.session.id
    for i in range(5):
        word = r.candidates[0] if r.candidates else "测试词"
        s = await engine.submit_word(sid, word, 1200 + i * 250, "selected")
        print(
            f"[submit] round={s.round} seed={s.current_seed} word={s.node.text} "
            f"emo={s.node.emotion_type} total={s.node.scores.total:.3f} "
            f"rt={s.node.reaction_time_ms} finished={s.finished}"
        )
        print(f"         next_cands={s.candidates[:4]}")
        if s.finished:
            break

    net = engine.get_network(sid)
    print(f"[network] nodes={len(net['nodes'])} edges={len(net['edges'])}")
    for n in net["nodes"][:8]:
        print(f"    node: {n['text']} {n['emotion_type']} total={n['total']:.3f} {n['color']}")
    for e in net["edges"][:5]:
        print(f"    edge: {e}")


if __name__ == "__main__":
    asyncio.run(main())
