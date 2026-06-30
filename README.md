# ChatMaster

一个多身份（multi-identity）的 AI 聊天智能体。每个身份（法律专家 / 情感大师 / 职业 prompt 工程师，……）都基于**自己的 RAG 知识库**回答问题，支持流式输出与引用来源。身份是「配置即数据」——新增身份只需改一个 YAML 文件，无需写代码。

AI 编排层使用 [LangChain](https://python.langchain.com)（结构上为后续升级 LangGraph 留好接口），HTTP 层使用 FastAPI，向量库使用 Qdrant，前端是 React + Vite。**API 配置（对话模型 / 向量模型的 base_url、key、模型名）可在 Web 页面运行时自定义**，无需改代码或重启。

> 架构说明：当前重构目标是本地 / 小团队 MVP，同时保留后续多用户上线能力。业务数据使用 SQLite（可迁移到 PostgreSQL），向量数据使用 Qdrant，RAG 工作流逐步迁移到 LangGraph。详见 `docs/architecture.md`。

---

## ✨ 特性

- **多身份 RAG**：每个身份一个私有知识库 + 全员共享的通用知识库，检索时用加权 **RRF（Reciprocal Rank Fusion）** 融合两路结果。
- **流式对话**：SSE 逐 token 输出，附带命中的知识来源（文件名 + 所属库 + 相关度）。
- **API 配置可视化**：内置「API 配置」页面，可填入任意 OpenAI 兼容服务（DeepSeek / Moonshot / OpenAI……）或 Anthropic，以及向量模型（本地 HuggingFace / OpenAI 兼容），并带「测试连接」按钮。
- **知识库管理**：支持 CLI 批量导入 + Web 上传，文档格式 txt / md / pdf / docx。
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

### 0. 准备 Python 环境（建议独立 conda 环境）

```bash
conda create -n chatmaster python=3.12 -y
conda activate chatmaster
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
pip install -e .          # 或 pip install -e ".[dev]"
```

编辑 `backend/.env`，至少填入一个对话模型的 API key（DeepSeek 示例）：

```dotenv
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.deepseek.com/v1
DEFAULT_GENERATION_MODEL=deepseek-v4-pro
DEFAULT_EMBEDDING_PROVIDER=huggingface
DEFAULT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
HUGGINGFACE_ENDPOINT=https://hf-mirror.com      # 国内镜像，避免下载超时
PROVIDERS_FILE=data/providers.json
```

> 说明：`.env` 里的 provider 配置只是**首次启动的种子**。启动后会写入 `data/providers.json`，之后以「API 配置」页面里保存的为准。也可设置环境变量 `HF_ENDPOINT=https://hf-mirror.com` 确保模型下载走镜像。

### 3. 启动后端

```bash
uvicorn chatmaster.main:app --reload --port 8000
```

首次启动会自动下载 embedding 模型（约 100MB，走镜像）并为每个身份创建私有集合 + 通用集合。看到 `ChatMaster ready. Collections ensured: [...]` 即就绪。

### 4. 导入知识库

```bash
# 从 backend/ 目录
python -m chatmaster.cli.ingest --identity legal_expert --path ./data/sample_docs/legal_expert
python -m chatmaster.cli.ingest --identity legal_expert --path ./data/sample_docs/common --common
```

也可启动前端后用网页上传。

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
  -d '{"identity_id":"legal_expert","message":"你好，介绍一下你自己","history":[]}'
```
SSE 事件流：`sources` → 多个 `token` → `done`。

---

## ⚙️ API 配置（运行时自定义）

「API 配置」页面（`GET/PUT /api/providers`）让你不改代码、不重启即可切换模型与凭据：

- **对话模型**：提供商（OpenAI 兼容 / Anthropic）、Base URL、API Key、模型名。
- **向量模型**：提供商（HuggingFace 本地 / OpenAI 兼容）、Base URL、API Key、模型名、HF 镜像。
- **保存即生效**：会清空已缓存的模型/向量/store 实例，下次请求用新配置重建。
- **安全**：读取时 API key 脱敏（`sk-****fade`）；提交空值或脱敏值时保留原 key，不会被覆盖。
- **测试连接**：`POST /api/providers/test` 分别试调对话模型与向量模型，返回 ok / 错误信息。

> 注意：切换向量模型会导致维度变化，已有的知识库需重新导入（页面有提示）。

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
| POST | `/api/chat` | SSE 流式对话：`sources` / `token` / `done` / `error` |
| POST | `/api/documents/ingest` | 多文件上传入库（multipart） |
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
