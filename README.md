# 联想情结探测工具

> 精神分析学派「词语联想实验」+ 荣格情结理论的 AI 增强实现。
> 通过「种子词 → 候选联想 → 反应时 → 多维评分 → 潜意识网络 → 分析报告」探测联想链背后的情绪敏感点（潜在情结）。

**当前进度：M1（核心实验循环）已完成并可运行。** M2（可视化）/ M3（分析与报告）待开发。

## 快速开始

无需安装任何新依赖（后端使用环境里已内置的 `aiohttp`，前端为免构建静态页）。

```bash
cd backend
python -m app.main
```

然后浏览器打开 **http://127.0.0.1:8000** 即可开始联想。

- 未配置 LLM key 时自动使用**离线 mock**（仅用于跑通流程）；
- 配置 DeepSeek 后切换为真实候选词生成与情绪标注。

### 接入真实 LLM（DeepSeek）

```bash
cd backend
copy .env.example .env   # 或手动创建 .env
# 编辑 .env，填入：
#   LLM_API_KEY=sk-xxxx
```

可选：接入真实 embedding（OpenAI 兼容）以启用有语义的相似度评分：

```bash
# .env 中追加
EMBEDDING_PROVIDER=api
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_API_KEY=sk-xxxx
EMBEDDING_MODEL=text-embedding-3-small
```

## 目录结构

```
Association/
  docs/            # 设计文档（数据模型/评分/API/候选/网络）
  backend/
    app/
      main.py      # aiohttp 入口（REST API + 静态前端托管）
      config.py    # 环境变量配置
      schemas.py   # Pydantic 数据模型
      constants.py # 情绪类型/颜色映射
      embeddings.py# embedding（字符 n-gram 离线 / API）
      llm/         # LLM 提供方（deepseek/ollama/mock）
      services/    # engine / store / scoring / network / candidates
    smoke_test.py  # 进程内冒烟测试
    http_test.py   # HTTP 冒烟测试
    requirements.txt
    .env.example
  frontend/        # 免构建静态前端
    index.html
    app.js
    style.css
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/sessions` | 创建会话（种子词） |
| GET | `/api/v1/sessions/{id}` | 获取会话状态与候选 |
| POST | `/api/v1/sessions/{id}/submit` | 提交一次联想（词 + 反应时） |
| POST | `/api/v1/sessions/{id}/reshuffle` | 刷新候选（不记录） |
| POST | `/api/v1/sessions/{id}/finish` | 提前结束 |
| GET | `/api/v1/sessions/{id}/network` | 获取网络（节点 + 边） |
| POST | `/api/v1/sessions/{id}/report` | 生成报告（M3，暂未实现） |

完整契约见 [docs/04-API接口.md](docs/04-API接口.md)。

## 说明与限制

- **探索性自省工具，非临床诊断。**
- 离线 `char_ngram` embedding 仅按字符重合计算，**语义相似度维度在离线模式下基本为 0**；接真实 embedding API 后才有意义。
- 后端为单进程内存存储，重启即清空；后续接 SQLite。
- 技术栈说明：因当前开发环境无外网，M1 采用 `aiohttp` + 免构建前端；联网后可平替 FastAPI + React（见 `docs/README.md`）。
