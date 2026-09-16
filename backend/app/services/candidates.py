"""候选词生成（全局结构感知 + 多样性，见 docs/05-候选词与back机制.md）。"""
from __future__ import annotations

from ..embeddings import dot
from ..llm import LLMProvider
from ..schemas import CandidateMeta, Session

SYSTEM = (
    "你是荣格式词语联想实验的联想助手。"
    "你的任务是生成多样化、有心理学价值的联想候选词，帮助被试进行自由联想。"
)


def _chain_texts(session: Session, seed: str) -> list[str]:
    for ch in session.chains:
        if ch.seed == seed:
            return [session.nodes[nid].text for nid in ch.node_ids]
    return []


def _build_user_prompt(
    session: Session, current_seed: str, current_word: str, n: int
) -> str:
    ns = session.network_state
    struct = (
        f"核心词={ns.top_central_words or ns.centroid_words or '无'};"
        f"主导情绪={ns.dominant_emotion};已现词={ns.node_count}个"
    )
    chain_str = current_seed + "".join(
        " → " + t for t in _chain_texts(session, current_seed)
    )
    return (
        f"给定种子词、当前词、联想链历史与当前网络结构摘要，生成 {n} 个联想候选词。\n"
        "【硬性多样性要求】候选必须覆盖多个维度，禁止全是同义词或同类词：\n"
        "1. 词类：具体事物 / 抽象概念 / 动作(动词) / 感受·情绪词 / 人物·关系 / "
        "地点·场景 / 感官(视听味触嗅) / 时间·记忆，尽量各出现；\n"
        "2. 语义距离：近(直接相关) / 中(间接) / 远(跳跃·诗性·自由联想)，远距离至少 3 个；\n"
        "3. 情绪效价：积极 / 消极 / 中性 / 矛盾·复杂，尽量都覆盖，避免清一色中性。\n"
        "禁止：与历史词重复、全部为双字常见名词、过度安全的同义联想。\n"
        "每个候选 1~6 字。只输出 JSON 数组：[\"词1\", \"词2\", ...]\n\n"
        f"种子词：{current_seed}\n"
        f"当前词：{current_word}\n"
        f"历史链：{chain_str}\n"
        f"网络结构：{struct}"
    )


def _mmr_select(items: list[dict], k: int, lam: float = 0.7) -> list[dict]:
    """贪心 MMR：平衡「分数」与「与已选集合的差异」，选出 k 个多样候选。"""
    selected: list[dict] = []
    remaining = list(items)
    while remaining and len(selected) < k:
        if not selected:
            best = max(remaining, key=lambda x: x["score"])
        else:
            def mmr(item: dict) -> float:
                sim = max(dot(item["emb"], s["emb"]) for s in selected)
                return lam * item["score"] - (1.0 - lam) * sim

            best = max(remaining, key=mmr)
        selected.append(best)
        remaining.remove(best)
    return selected


async def generate_candidates(
    session: Session,
    current_seed: str,
    current_word: str,
    store,
    llm: LLMProvider,
    config,
) -> tuple[list[str], list[CandidateMeta]]:
    messages = [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": _build_user_prompt(
                session, current_seed, current_word, config.candidate_generate_n
            ),
        },
    ]
    raw = await llm.complete_json(messages, config.temperature)

    cands: list[str] = []
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, str):
                t = c.strip()
                if t and t not in cands:
                    cands.append(t)

    existing = [n.text for n in session.nodes.values()]
    existing_vecs = [store.embed(t) for t in existing]
    centroid = store.centroid_embedding(session)

    scored: list[dict] = []
    for text in cands:
        emb = store.embed(text)
        max_sim = max((dot(emb, v) for v in existing_vecs), default=0.0)
        is_back = text in existing
        if not is_back and max_sim >= config.dedup_threshold:
            continue  # 近重复且非历史词 → 丢弃
        if is_back:
            occ = next(
                (n.occurrences for n in session.nodes.values() if n.text == text), 1
            )
            if occ >= 2:
                continue  # 高频历史词不再推荐

        novelty = 1.0 - max_sim
        fit = dot(emb, centroid) if centroid is not None else 0.0
        score = 0.5 * novelty + 0.5 * fit
        if is_back:
            score *= config.back_penalty
        scored.append({"score": score, "text": text, "is_back": is_back, "emb": emb})

    top = _mmr_select(scored, config.candidate_count)

    metas = [
        CandidateMeta(
            text=item["text"],
            source="back" if item["is_back"] else "llm",
            is_back=item["is_back"],
            penalty=round(config.back_penalty if item["is_back"] else 0.0, 2),
        )
        for item in top
    ]
    return [item["text"] for item in top], metas
