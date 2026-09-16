"""报告生成（M3）：LLM 结合统计与情结候选，生成自然语言解读。"""
from __future__ import annotations

from ..llm import LLMProvider
from ..schemas import Session
from .analysis import analyze

SYSTEM = (
    "你是一位温和、审慎的心理联想分析助手，基于荣格词语联想实验的数据做解读。"
    "你的解读用于自我觉察与反思，必须避免诊断式断言，不夸大、不贴标签，"
    "多用「可能 / 或许 / 值得留意」等措辞。"
)

DISCLAIMER = (
    "本报告由探索性自省工具自动生成，仅用于自我觉察与反思参考，"
    "不构成任何临床诊断或专业建议。"
)


def _build_user_prompt(session: Session, analysis: dict) -> str:
    s = analysis["stats"]
    lines: list[str] = []
    lines.append("种子词：" + "、".join(session.seed_words))
    lines.append(
        f"共 {s['word_count']} 个联想词、{s['edge_count']} 条联想路径；"
        f"主导情绪 {s['dominant_emotion_label']}；情绪分布 {s['emotion_distribution']}。"
    )
    lines.append("核心词（综合分最高）：" + ("、".join(analysis["core_words"]) or "无"))
    lines.append(
        "反应时明显偏长的词（可能触及敏感点）："
        + ("、".join(s["anomalous_rt_nodes"]) or "无")
    )
    lines.append("")
    lines.append("联想链：")
    for ch in session.chains:
        words = [session.nodes[nid].text for nid in ch.node_ids]
        chain_str = ch.seed + (" → " + " → ".join(words) if words else "")
        lines.append("  " + chain_str)

    top = analysis["complexes"][:3]
    lines.append("")
    lines.append("情结候选（按 signal 从高到低，请逐一解读）：")
    for c in top:
        lines.append(
            f"  [{c['emotion']}|{c['emotion_label']}] 核心={c['core']} "
            f"signal={c['signal']} 词={'、'.join(c['nodes'])}"
        )
    lines.append("")
    lines.append(
        "请输出 JSON：{\"summary\": \"整体解读（150~300字）\", "
        "\"complexes\": [{\"emotion\": \"英文情绪名\", \"description\": \"该情绪簇的可能含义（50~100字）\"}]}"
    )
    lines.append("complexes 必须逐一对应上面列出的情结候选，emotion 用英文名。")
    return "\n".join(lines)


async def build_report(session: Session, llm: LLMProvider, config) -> dict:
    analysis = analyze(session)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": _build_user_prompt(session, analysis)},
    ]
    try:
        result = await llm.complete_json(messages, config.temperature)
    except Exception:
        result = {}
    if not isinstance(result, dict):
        result = {}

    summary = str(result.get("summary", "") or "")
    descs = result.get("complexes", []) or []
    desc_map: dict[str, str] = {}
    if isinstance(descs, list):
        for d in descs:
            if isinstance(d, dict) and d.get("emotion"):
                desc_map[str(d["emotion"])] = str(d.get("description", "") or "")

    complexes_out = []
    for c in analysis["complexes"][:3]:
        complexes_out.append(
            {
                "emotion": c["emotion"],
                "emotion_label": c["emotion_label"],
                "core": c["core"],
                "nodes": c["nodes"],
                "signal": c["signal"],
                "description": desc_map.get(c["emotion"], ""),
            }
        )

    return {
        "summary": summary,
        "complexes": complexes_out,
        "stats": analysis["stats"],
        "core_words": analysis["core_words"],
        "disclaimer": DISCLAIMER,
    }
