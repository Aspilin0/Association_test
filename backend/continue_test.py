"""验证「继续联想」：固定轮数跑满后不自动结束，可继续提交。"""
import asyncio

from app import embeddings as emb_mod
from app import llm as llm_mod
from app.config import Config
from app.schemas import CreateSessionRequest, Options
from app.services.engine import Engine
from app.services.store import SessionStore


async def main() -> None:
    c = Config()
    c.llm_provider = "mock"
    c.embedding_provider = "char_ngram"
    eng = Engine(c, llm_mod.get_provider(c), SessionStore(emb_mod.get_provider(c)))

    r = await eng.create_session(
        CreateSessionRequest(seed_words=["家"], options=Options(rounds_per_seed=2))
    )
    sid = r.session.id
    print("create: seed=", r.current_seed, "round=1")

    for i in range(1, 5):
        w = r.candidates[0] if r.candidates else f"词{i}"
        s = await eng.submit_word(sid, w, 1000 + i * 50, "selected")
        st = eng.get_state(sid)
        print(
            f"submit{i}: word={s.node.text} round={s.round} "
            f"rounds_complete={s.rounds_complete} finished={s.finished} "
            f"status={st.session.status}"
        )
        r = st

    print("final status:", eng.get_state(sid).session.status)


if __name__ == "__main__":
    asyncio.run(main())
