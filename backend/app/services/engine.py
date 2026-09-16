"""会话引擎：串联 评分 / 候选 / 网络 / 存储。"""
from __future__ import annotations

from datetime import datetime, timezone

from ..constants import EMOTION_TYPES
from ..llm import LLMProvider
from ..schemas import (
    Baseline,
    CandidateMeta,
    Chain,
    CreateSessionRequest,
    Edge,
    Options,
    Scores,
    Session,
    SessionStateResponse,
    SubmitResponse,
    WordNode,
)
from .candidates import generate_candidates
from .report import build_report
from .network import (
    build_network_response,
    compute_degree,
    compute_network_state,
)
from .scoring import (
    connectivity_score,
    rt_score,
    rt_zscore,
    similarity_score,
    total_score,
    update_baseline,
)
from .store import SessionStore, new_id

EMOTION_SYSTEM = (
    "你是情绪标注器。对给定词语，判断其最主导的情绪类型与强度。\n"
    "情绪类型（Plutchik 8 类 + 中性）及典型联想：\n"
    "- joy 快乐：喜悦、满足、爱、温暖、家、阳光\n"
    "- trust 信任：依赖、安心、信仰、忠诚\n"
    "- fear 恐惧：危险、黑暗、失控、坠落\n"
    "- surprise 惊讶：意外、突然、震撼、回头\n"
    "- sadness 悲伤：失落、离别、孤独、眼泪、记忆\n"
    "- disgust 厌恶：恶心、排斥、污秽\n"
    "- anger 愤怒：仇恨、冲突、暴躁、火\n"
    "- anticipation 期待：希望、计划、未来、憧憬、远方\n"
    "- neutral 中性：无明显情绪（仅限真正中性的词）\n"
    "要求：尽量使用全部 8 类，不要默认 neutral；一词含多重情绪时取更强烈者；\n"
    "emotion_intensity 用 0~1 浮点，保留一位小数。\n"
    "只输出 JSON：{\"emotion_type\": \"...\", \"emotion_intensity\": 0.0~1.0}"
)


class AppError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        self.message = message or code
        super().__init__(message or code)


class Engine:
    def __init__(self, config, llm: LLMProvider, store: SessionStore) -> None:
        self.config = config
        self.llm = llm
        self.store = store
        self._emotion_cache: dict[str, tuple[str, float]] = {}
        self._candidates: dict[str, list[str]] = {}
        self._candidates_meta: dict[str, list[CandidateMeta]] = {}

    # ---- 工具 ----
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _tag_emotion(self, text: str) -> tuple[str, float]:
        if text in self._emotion_cache:
            return self._emotion_cache[text]
        obj = await self.llm.complete_json(
            [
                {"role": "system", "content": EMOTION_SYSTEM},
                {"role": "user", "content": f"词语：{text}"},
            ],
            0.0,
        )
        if isinstance(obj, dict):
            etype = str(obj.get("emotion_type", "neutral"))
            try:
                intensity = float(obj.get("emotion_intensity", 0.0))
            except (TypeError, ValueError):
                intensity = 0.0
        else:
            etype = "neutral"
            intensity = 0.0
        if etype not in EMOTION_TYPES:
            etype = "neutral"
        intensity = max(0.0, min(1.0, intensity))
        self._emotion_cache[text] = (etype, intensity)
        return etype, intensity

    def _current_chain(self, session: Session):
        """返回当前应追加的链：固定阶段=第一条未满链；扩展阶段=最后一条链。"""
        for ch in session.chains:
            if len(ch.node_ids) < session.options.rounds_per_seed:
                return ch
        if session.chains:
            return session.chains[-1]
        return None

    def _is_rounds_complete(self, session: Session) -> bool:
        """是否所有种子固定轮数都已跑满（进入可继续联想的扩展阶段）。"""
        if not session.chains:
            return False
        return all(
            len(ch.node_ids) >= session.options.rounds_per_seed
            for ch in session.chains
        )

    def _current_word(self, session: Session, chain: Chain) -> str:
        if chain.node_ids:
            return session.nodes[chain.node_ids[-1]].text
        return chain.seed

    def _chain_texts(self, session: Session, chain: Chain) -> list[str]:
        return [session.nodes[nid].text for nid in chain.node_ids]

    def _get_session(self, session_id: str) -> Session:
        session = self.store.get(session_id)
        if session is None:
            raise AppError("SESSION_NOT_FOUND", "会话不存在")
        return session

    # ---- 建会话 ----
    async def create_session(self, req: CreateSessionRequest) -> SessionStateResponse:
        seeds: list[str] = []
        for s in req.seed_words:
            s = s.strip()
            if s and s not in seeds:
                seeds.append(s)
        if not seeds:
            raise AppError("INVALID_INPUT", "seed_words 不能为空")

        options = req.options or Options()
        session = Session(
            id=new_id(),
            seed_words=seeds,
            options=options,
            status="running",
            created_at=self._now(),
            baseline=Baseline(
                mean_rt_ms=self.config.baseline_mean_ms,
                std_rt_ms=self.config.baseline_std_ms,
                n=0,
            ),
        )

        for seed in seeds:
            etype, intensity = await self._tag_emotion(seed)
            node = WordNode(
                id=new_id(),
                text=seed,
                emotion_type=etype,
                emotion_intensity=intensity,
                order=0,
                source="seed",
                seed_of=seed,
                created_at=self._now(),
            )
            session.nodes[node.id] = node
            session.history.append(seed)
            session.chains.append(Chain(seed=seed))

        session.network_state = compute_network_state(session, self.store)
        self.store.put(session)

        chain = self._current_chain(session)
        seed = chain.seed
        word = self._current_word(session, chain)
        cands, metas = await generate_candidates(
            session, seed, word, self.store, self.llm, self.config
        )
        self._candidates[session.id] = cands
        self._candidates_meta[session.id] = metas
        return SessionStateResponse(
            session=session,
            current_seed=seed,
            round=1,
            candidates=cands,
            candidates_meta=metas,
        )

    # ---- 提交一次联想 ----
    async def submit_word(
        self, session_id: str, word: str, rt_ms: int, source: str
    ) -> SubmitResponse:
        session = self._get_session(session_id)
        if session.status == "finished":
            raise AppError("SESSION_FINISHED", "会话已结束")

        word = word.strip()
        if not word:
            raise AppError("INVALID_WORD", "词语不能为空")

        chain = self._current_chain(session)
        if chain is None:
            raise AppError("SESSION_FINISHED", "会话已结束")

        seed = chain.seed
        round_no = len(chain.node_ids) + 1
        prev_id = (
            chain.node_ids[-1]
            if chain.node_ids
            else self.store.text_to_node_id(session)[seed]
        )
        prev_text = session.nodes[prev_id].text if prev_id in session.nodes else seed

        is_back = word in session.history

        # 情绪
        etype, intensity = await self._tag_emotion(word)

        # 嵌入
        emb_word = self.store.embed(word)
        emb_seed = self.store.embed(seed)
        emb_prev = self.store.embed(prev_text)
        emb_global = self.store.centroid_embedding(session)  # 加入前的全局结构

        # 反应时
        base = session.baseline
        z = rt_zscore(rt_ms, base.mean_rt_ms, base.std_rt_ms)
        s_rt = rt_score(z)
        if is_back:
            s_rt = min(1.0, s_rt + self.config.rt_back_bonus)
        new_mean, new_std, new_n = update_baseline(
            base.mean_rt_ms, base.std_rt_ms, base.n, rt_ms, self.config.baseline_alpha
        )
        session.baseline = Baseline(mean_rt_ms=new_mean, std_rt_ms=new_std, n=new_n)

        # 相似度（全局结构）
        s_sim = similarity_score(
            emb_word,
            emb_seed,
            emb_prev,
            emb_global,
            has_prev=bool(chain.node_ids),
            w_seed=self.config.sim_w_seed,
            w_prev=self.config.sim_w_prev,
            w_global=self.config.sim_w_global,
        )

        # 节点：复用或新建（同一词全局唯一，occurrences 累加）
        text_to_id = self.store.text_to_node_id(session)
        if word in text_to_id:
            node = session.nodes[text_to_id[word]]
            node.occurrences += 1
            node.is_back = True
        else:
            node = WordNode(
                id=new_id(),
                text=word,
                emotion_type=etype,
                emotion_intensity=intensity,
                order=round_no,
                source=source,
                is_back=is_back,
                occurrences=1,
                seed_of=seed,
                created_at=self._now(),
            )
            session.nodes[node.id] = node

        node.emotion_type = etype
        node.emotion_intensity = intensity
        node.source = source
        node.seed_of = seed
        node.order = round_no
        node.reaction_time_ms = rt_ms
        node.rt_zscore = round(z, 4)

        # 边：association prev -> node
        session.edges.append(
            Edge(id=new_id(), frm=prev_id, to=node.id, type="association", weight=1.0)
        )

        # 连接量
        deg = compute_degree(session)
        s_conn = connectivity_score(deg.get(node.id, 0), node.occurrences)

        # 综合分
        s_emotion = intensity
        total = total_score(s_rt, s_emotion, s_sim, s_conn, self.config)
        node.scores = Scores(
            emotion=round(s_emotion, 4),
            similarity=round(s_sim, 4),
            connectivity=round(s_conn, 4),
            reaction_time=round(s_rt, 4),
            total=round(total, 4),
        )

        chain.node_ids.append(node.id)
        session.history.append(word)
        session.network_state = compute_network_state(session, self.store)

        # 推进：固定轮数内切到下一个种子；跑满后进入扩展阶段（可继续联想，不自动结束）
        rounds_complete = self._is_rounds_complete(session)
        next_chain = self._current_chain(session)
        current_seed = next_chain.seed if next_chain else seed
        cur_word = self._current_word(session, next_chain) if next_chain else word
        cands, metas = await generate_candidates(
            session, current_seed, cur_word, self.store, self.llm, self.config
        )
        self._candidates[session.id] = cands
        self._candidates_meta[session.id] = metas

        chain_texts = [seed] + self._chain_texts(session, chain)
        return SubmitResponse(
            node=node,
            round=round_no,
            current_seed=current_seed,
            finished=False,
            rounds_complete=rounds_complete,
            chain=chain_texts,
            candidates=cands,
            candidates_meta=metas,
        )

    # ---- 状态 / 刷新 / 结束 / 网络 ----
    def get_state(self, session_id: str) -> SessionStateResponse:
        session = self._get_session(session_id)
        chain = self._current_chain(session)
        if chain is None:
            current_seed = session.seed_words[-1] if session.seed_words else ""
            round_no = 0
        else:
            current_seed = chain.seed
            round_no = len(chain.node_ids) + 1
        return SessionStateResponse(
            session=session,
            current_seed=current_seed,
            round=round_no,
            rounds_complete=self._is_rounds_complete(session),
            candidates=self._candidates.get(session_id, []),
            candidates_meta=self._candidates_meta.get(session_id, []),
        )

    async def reshuffle(self, session_id: str) -> SessionStateResponse:
        session = self._get_session(session_id)
        chain = self._current_chain(session)
        if chain is None:
            raise AppError("SESSION_FINISHED", "会话已结束")
        seed = chain.seed
        word = self._current_word(session, chain)
        cands, metas = await generate_candidates(
            session, seed, word, self.store, self.llm, self.config
        )
        self._candidates[session_id] = cands
        self._candidates_meta[session_id] = metas
        return SessionStateResponse(
            session=session,
            current_seed=seed,
            round=len(chain.node_ids) + 1,
            rounds_complete=self._is_rounds_complete(session),
            candidates=cands,
            candidates_meta=metas,
        )

    def finish(self, session_id: str) -> Session:
        session = self._get_session(session_id)
        if session.status != "finished":
            session.status = "finished"
            session.finished_at = self._now()
        return session

    def get_network(self, session_id: str) -> dict:
        session = self._get_session(session_id)
        return build_network_response(session)

    async def generate_report(self, session_id: str) -> dict:
        session = self._get_session(session_id)
        return await build_report(session, self.llm, self.config)
