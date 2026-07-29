# ChatMaster

一个多身份（multi-identity）的 AI 聊天智能体。每个身份（法律专家 / 情感大师 / 职业 prompt 工程师，……）都基于**自己的 RAG 知识库**回答问题，支持流式输出与引用来源。身份是「配置即数据」——新增身份只需改一个 YAML 文件，无需写代码。

RAG 对话工作流使用 [LangGraph](https://langchain-ai.github.io/langgraph/)，HTTP 层使用 FastAPI，业务数据使用 SQLite，向量库使用 Qdrant，前端是 React + Vite。**API 配置（对话模型 / 向量模型的 base_url、key、模型名）可在 Web 页面运行时自定义**，无需改代码或重启。

> 架构说明：当前重构目标是本地 / 小团队 MVP，同时保留后续多用户上线能力。业务数据使用 SQLite（可迁移到 PostgreSQL），向量数据使用 Qdrant，RAG 工作流逐步迁移到 LangGraph。详见 `docs/architecture.md`。

---

## ✨ 特性

- **多身份 RAG**：每个身份一个私有知识库 + 全员共享的通用知识库，检索时用加权 **RRF（Reciprocal Rank Fusion）** 融合两路结果。
- **可靠流式对话**：SSE 逐 token 输出，支持停止、幂等 request_id、持久化部分回答与逐消息引用来源。
- **API 配置可视化**：内置「API 配置」页面，可填入任意 OpenAI 兼容服务（DeepSeek / Moonshot / OpenAI……）或 Anthropic，以及向量模型（本地 HuggingFace / OpenAI 兼容），并带「测试连接」按钮。
- **知识库管理**：支持 CLI 批量导入 + Web 后台上传、失败重试、删除与非破坏式索引重建。
- **配置即数据**：身份、system prompt、检索参数全部写在 `identities.yaml`。
- **LangGraph-ready**：AI 层按 retrieve → augment → generate 切分，后续可平滑迁移到 `StateGraph`。

---

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 · FastAPI · pydantic-settings · sse-starlette |
| AI 编排 | LangChain 1.x（langchain-openai / langchain-anthropic / langchain-qdrant / langchain-huggingface） |
| 向量库 | Qdrant（docker-compose，或 `:memory:` 用于测试） |
| 向量模型 | HuggingFace 本地（默认 `BAAI/bge-small-zh-v1.5`，512 维，免费无 key）/ OpenAI 兼容 |
| 对话模型 | OpenAI 兼容（默认 DeepSeek）/ Anthropic |
| 前端 | React 18 · TypeScript · Vite · `@microsoft/fetch-event-source`（POST + SSE） |

---

## 📂 项目结构

```
ChatMaster/
├── docker-compose.yml              # Qdrant (6333 REST / 6334 gRPC)
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── .env                        # 本地配置（已 gitignore，不会上传）
│   ├── data/
│   │   ├── sample_docs/            # 示例文档（每个身份一个子目录 + common/）
│   │   └── providers.json          # 运行时 API 配置（首次从 .env 生成）
│   └── chatmaster/
│       ├── main.py                 # FastAPI app 工厂 + lifespan
│       ├── config.py               # pydantic-settings（.env 读取 + 缓存）
│       ├── identities/
│       │   ├── schema.py           # IdentityConfig / RetrievalConfig
│       │   ├── loader.py           # YAML 加载 + 校验 + registry
│       │   └── identities.yaml     # ← 身份定义（可扩展）
│       ├── ai/                     # LangChain AI 层（无 FastAPI 依赖）
│       │   ├── providers.py        # 运行时可自定义的 provider 配置（持久化）
│       │   ├── models.py           # build_chat_model / build_embeddings 工厂
│       │   ├── loaders.py          # 按扩展名分发 DocumentLoader
│       │   ├── chunkers.py         # CJK 友好的递归切分
│       │   ├── vectorstore.py      # QdrantVectorStore 封装 + 集合管理
│       │   ├── retriever.py        # 混合检索 + 加权 RRF 融合
│       │   ├── prompts.py          # persona + 参考资料 提示模板
│       │   └── chain.py            # retrieve → augment → generate 流式链
│       ├── services/
│       │   ├── chat_service.py     # 链 → SSE 事件适配
│       │   └── ingest_service.py   # 加载 → 切分 → 嵌入 → 入库
│       ├── routers/
│       │   ├── chat.py             # POST /api/chat（SSE）
│       │   ├── identities.py       # 身份列表/详情
│       │   ├── documents.py        # 文档上传入库
│       │   ├── providers.py        # API 配置 GET/PUT/测试
│       │   └── health.py
│       ├── schemas/api.py
│       └── cli/ingest.py           # typer 批量导入 CLI
└── frontend/
    ├── package.json
    ├── vite.config.ts              # 代理 /api → localhost:8000
    └── src/
        ├── App.tsx                 # 侧边栏 + 对话/设置 切换
        ├── api/{client,sse}.ts
        ├── hooks/{useIdentities,useChat,useUpload,useProviders}.ts
        ├── components/             # IdentitySelector / ChatWindow / ProviderSettings …
        └── types/api.ts
```

---

## 🚀 快速开始

### 0. 准备 Python 环境

```bash
conda activate chatmaster
# 若无环境：conda create -n chatmaster python=3.12 -y
```

### 1. 启动 Qdrant

```bash
docker compose up -d qdrant
# 验证：curl http://localhost:6333/healthz  →  healthz check passed
```

### 2. 配置后端

```bash
cp .env.example backend/.env
cd backend
pip install -e ".[dev]"
```

编辑 `backend/.env`，至少填入一个对话模型的 API key（DeepSeek 示例）：

```dotenv
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.deepseek.com/v1
DEFAULT_GENERATION_MODEL=deepseek-v4-pro
DEFAULT_EMBEDDING_PROVIDER=huggingface
DEFAULT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
HUGGINGFACE_ENDPOINT=https://hf-mirror.com      # 国内镜像，避免下载超时
PROVIDER_ENCRYPTION_KEY=请填入Fernet密钥
```

> 说明：`.env` 是首次种子；在「API 配置」页面保存后写入 SQLite `provider_configs`，之后以数据库为准。

### 3. 启动后端

```bash
uvicorn chatmaster.main:app --reload --host 127.0.0.1 --port 8000
```

首次启动只执行数据库迁移、种子数据和身份配置校验。Embedding 模型与 Qdrant
会在首次导入或聊天时按需初始化，因此外部服务暂不可用时仍可进入 API 配置页。

### 4. 导入知识库

```bash
python scripts/seed_sample_docs.py
# 或手动：python -m chatmaster.cli.ingest -i legal_expert -p ./data/sample_docs/legal_expert
```

CLI 与网页上传均写入 SQLite，在「知识库」页可见。

### 5. 启动前端

```bash
cd ../frontend
npm install
npm run dev          # http://localhost:5173
```

打开页面 → 选择身份 → 在侧边栏点「⚙ API 配置」填好 base_url / key / 模型 → 保存（可点「测试连接」）→ 回到对话即可聊天。

### 6. 命令行快速验证（可选）

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"request_id":"00000000-0000-4000-8000-000000000001","identity_id":"legal_expert","message":"你好，介绍一下你自己"}'
```
SSE 事件流：`sources` → 多个 `token` → `done`。停止生成可调用
`POST /api/chat/{request_id}/cancel`；`done.status` 为 `complete` 或 `stopped`。

---

## ⚙️ API 配置（运行时自定义）

「API 配置」页面（`GET/PUT /api/providers`）让你不改代码、不重启即可切换模型与凭据：

- **对话模型**：提供商（OpenAI 兼容 / Anthropic）、Base URL、API Key、模型名。
- **向量模型**：提供商（HuggingFace 本地 / OpenAI 兼容）、Base URL、API Key、模型名、HF 镜像。
- **保存即生效**：会清空已缓存的模型/向量/store 实例，下次请求用新配置重建。
- **安全**：读取时 API key 脱敏（`sk-****fade`）；提交空值或脱敏值时保留原 key，不会被覆盖。
- **安全**：凭据仅加密写入 SQLite；旧版 `providers.json` 不再被读取。需要迁移时执行 `chatmaster-import-legacy-providers --path data/providers.json --confirm`，确认后再手动删除明文文件。
- **地址限制**：仅支持 HTTP(S)；本机回环模型服务可直接使用，局域网地址需设置 `ALLOW_PRIVATE_PROVIDER_URLS=true`。
- **测试连接**：`POST /api/providers/test` 分别试调对话模型与向量模型，失败详情仅写入服务端日志。

> 注意：切换向量模型会导致维度变化，已有知识库必须重建索引。

切换 embedding provider 或模型后，请使用非破坏式重建命令创建新索引版本；它会在全部文档重嵌入成功后才切换，旧版本会保留：

```bash
chatmaster-rebuild-index --identity legal_expert --confirm
# 重建共享知识库：chatmaster-rebuild-index --common --confirm
# 预览过期/失败索引：chatmaster-cleanup-indexes
# 确认删除：chatmaster-cleanup-indexes --confirm
```

---

## 🧩 扩展指南

### 新增身份（无需写代码）

1. 在 `backend/chatmaster/identities/identities.yaml` 追加一个条目（id / name / system_prompt / private_collection / retrieval）。
2. 重启后端——lifespan 会自动创建新的私有集合。
3. 导入文档：CLI 或网页上传。
4. 身份立即出现在选择器里。

### 切换模型

- **对话模型**：在「API 配置」页面改；或给单个身份在 YAML 里设 `generation_model` 覆盖模型名。
- **向量模型**：在「API 配置」页面改（切维度需重新导入）。
- **换向量库**：只有 `ai/vectorstore.py` 封装了 `QdrantVectorStore`，换个 LangChain `VectorStore` 实现即可。

### 升级到 LangGraph

`ai/chain.py` 的 retrieve → augment → generate 三步可直接映射为 `StateGraph` 的三个节点；`chat_service` 改为消费 graph 事件流即可，AI 层边界已为此切分好。

---

## 📡 API 一览

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查：当前 provider 配置、集合、身份 |
| GET | `/api/identities` | 身份列表（不含 system prompt） |
| GET | `/api/identities/{id}` | 单个身份详情 |
| POST | `/api/chat` | SSE 流式对话 |
| POST | `/api/conversations` | 创建会话 |
| GET | `/api/conversations` | 会话列表 |
| GET | `/api/conversations/{id}/messages` | 会话消息 |
| DELETE | `/api/conversations/{id}` | 删除会话 |
| POST | `/api/documents/ingest` | 提交后台文档导入任务（202） |
| POST | `/api/ingest-jobs/{id}/retry` | 重试失败导入 |
| DELETE | `/api/documents/{id}` | 删除文件、分块与向量 |
| GET | `/api/indexes` | 索引版本和新鲜度 |
| POST | `/api/indexes/rebuild` | 后台重建索引 |
| GET | `/api/providers` | 读取 API 配置（key 脱敏） |
| PUT | `/api/providers` | 保存 API 配置 |
| POST | `/api/providers/test` | 测试对话 + 向量连接 |

---

## 🔧 开发提示

- **Qdrant 版本警告**：客户端版本与 server 版本不一致会打印 `UserWarning`，功能不受影响。如需消除，把 `docker-compose.yml` 的 Qdrant 镜像升到与 `qdrant-client` minor 相近的版本。
- **Starlette 路由校验**：`include_router` 产生的是惰性 `_IncludedRouter`，不要靠遍历 `app.routes` 校验路由是否注册——直接用 httpx `ASGITransport` 打请求验证。
- **Windows npm 缓存权限**：若全局缓存目录 EPERM，用 `npm install --cache /tmp/npm-cache`。
- **HuggingFace 镜像**：必须在导入任何 `huggingface_hub` 相关库**之前**设 `HF_ENDPOINT`，否则镜像不生效（已在 `main.py` / `cli/ingest.py` 顶部默认设为 `https://hf-mirror.com`）。

---

## 📦 开发依赖

dev 附加项（`pip install -e ".[dev]"`）：`pytest`、`pytest-asyncio`、`httpx`、`ruff`。

## 📄 License

MIT
