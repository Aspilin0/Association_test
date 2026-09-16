# 04 — API 接口

Base URL：`/api/v1`。以下为前后端契约，后端 Pydantic 校验，前端 TS 类型对齐。

## 1. 创建会话

`POST /api/v1/sessions`

请求：

```json
{
  "seed_words": ["家", "母亲"],
  "options": {
    "rounds_per_seed": 10,
    "candidate_count": 8,
    "temperature": 0.9,
    "emotion_scheme": "plutchik",
    "llm_provider": "deepseek"
  }
}
```

响应 `200`：

```json
{
  "session": { "...Session，含 chains=[] 空链、baseline 初值..." },
  "current_seed": "家",
  "round": 1,
  "candidates": ["房子", "温暖", "童年", "窗", "锅", "门", "回忆", "远"],
  "candidates_meta": [
    { "text": "房子", "source": "llm", "is_back": false, "penalty": 0.0 }
  ]
}
```

## 2. 获取会话状态

`GET /api/v1/sessions/{id}`

响应：`{ "session": {...}, "current_seed": "...", "round": 5, "candidates": [...], "candidates_meta": [...] }`

## 3. 提交一次联想（核心）

`POST /api/v1/sessions/{id}/submit`

请求：

```json
{
  "word": "房子",
  "reaction_time_ms": 1234,
  "source": "selected"
}
```

> `source`：`selected`（点击候选）或 `free`（自由输入）。是否 `is_back` 由后端据 `history` 自动判定，前端无需传。

响应 `200`：

```json
{
  "node": { "...WordNode，含四维评分..." },
  "round": 5,
  "current_seed": "家",
  "finished": false,
  "chain": ["家", "房子"],
  "candidates": ["墙", "屋", "童年", "窗", "院子", "门", "回忆", "暖"],
  "candidates_meta": [ { "text": "墙", "source": "llm", "is_back": false, "penalty": 0.0 } ]
}
```

- `finished=true` 表示该种子链完成；后端会自动切换到下一个种子词，并返回新种子的首轮候选。
- 全部种子完成后 `finished=true` 且 `candidates=[]`，`session.status="finished"`。

## 4. 重新生成候选（不记录、不计时）

`POST /api/v1/sessions/{id}/reshuffle`

响应：与「获取状态」中候选部分相同，仅刷新当前候选池，不新增节点、不更新评分。

## 5. 提前结束

`POST /api/v1/sessions/{id}/finish`

响应：`{ "session": {...status="finished"...} }`

## 6. 获取网络（M2 可视化用）

`GET /api/v1/sessions/{id}/network`

响应：

```json
{
  "nodes": [ { "id": "n1", "text": "房子", "emotion_type": "sadness", "intensity": 0.72, "total": 0.61, "size": 12, "color": "#42A5F5" } ],
  "edges": [ { "from": "n1", "to": "n3", "type": "association", "weight": 1.0 } ]
}
```

> `size` 由 `total` 映射（如 `8 + 16·total`）；`color` 由情绪类映射。

## 7. 生成报告（M3）

`POST /api/v1/sessions/{id}/report`

响应：

```json
{
  "summary": "……自然语言解读……",
  "complexes": [
    { "core": "房子", "nodes": ["房子", "童年", "回忆"], "signal": 0.74, "description": "……" }
  ],
  "stats": { "node_count": 12, "edge_count": 15, "avg_rt_ms": 1350, "anomalous_rt_nodes": ["房子"] },
  "disclaimer": "本报告为探索性自省工具输出，非临床诊断。"
}
```

## 8. 错误约定

统一错误结构：

```json
{ "error": { "code": "SESSION_NOT_FOUND", "message": "会话不存在" } }
```

常见 code：`SESSION_NOT_FOUND` / `SESSION_FINISHED` / `INVALID_WORD` / `LLM_ERROR`。
