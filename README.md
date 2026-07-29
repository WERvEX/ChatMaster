# ChatMaster

一个多人格（multi-persona）的 AI 聊天智能体。每个人格（法律专家 / 情感大师 / 职业 prompt 工程师，……）都可以基于**自己的 RAG 知识库**回答问题，支持流式输出与引用来源。人格可直接在网页中创建、编辑、复制、归档与恢复，无需修改代码或重启服务。

RAG 对话工作流使用 [LangGraph](https://langchain-ai.github.io/langgraph/)，HTTP 层使用 FastAPI，业务数据使用 SQLite，向量库使用 Qdrant，前端是 React + Vite。**API 配置（对话模型 / 向量模型的 Base URL、密钥、模型名）可在 Web 页面运行时自定义**，无需改代码或重启。

> 当前版本面向本地 / 小团队 MVP，尚未提供登录与权限隔离，请勿直接暴露到公网。业务数据使用 SQLite（可迁移到 PostgreSQL），向量数据使用 Qdrant。详见[架构说明](docs/architecture.md)。

---

## ✨ 特性

- **多身份 RAG**：每个身份一个私有知识库 + 全员共享的通用知识库，检索时用加权 **RRF（Reciprocal Rank Fusion）** 融合两路结果。
- **可靠流式对话**：SSE 逐 token 输出，支持停止、幂等 request_id、持久化部分回答与逐消息引用来源。
- **API 配置可视化**：内置「API 配置」页面，可填入任意 OpenAI 兼容服务（DeepSeek / Moonshot / OpenAI……）或 Anthropic，以及向量模型（本地 HuggingFace / OpenAI 兼容），并带「测试连接」按钮。
- **知识库管理**：支持 CLI 批量导入 + Web 后台上传、失败重试、删除与非破坏式索引重建。
- **网页人格管理**：名称、头像、system prompt、模型覆盖和检索参数持久化到 SQLite；`identities.yaml` 仅用于首次初始化默认人格。
- **独立会话空间**：每个会话固定绑定一个人格，切换人格时恢复该人格最近使用的会话，避免上下文与私有知识库混用。
- **ChatGPT 风格网页**：可折叠会话侧边栏、移动端抽屉、会话自动命名/重命名/删除，以及位于聊天页顶部的人格选择器。
- **LangGraph 工作流**：`StateGraph` 显式编排人格加载、历史加载、知识检索和提示构建，服务层负责模型流式输出与消息持久化。

---

## 🧱 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+ · FastAPI · pydantic-settings · sse-starlette |
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
├── docs/architecture.md            # 架构、持久化和数据流说明
├── backend/
│   ├── pyproject.toml
│   ├── .env                        # 本地配置（已 gitignore，不会上传）
│   ├── data/
│   │   └── sample_docs/            # 示例文档（每个人格一个子目录 + common/）
│   └── chatmaster/
│       ├── main.py                 # FastAPI app、迁移、种子与任务恢复
│       ├── config.py               # 环境变量读取
│       ├── chat/                   # LangGraph 状态图、SSE 与持久化
│       ├── identities/             # 人格 CRUD、归档/恢复、YAML 初始种子
│       ├── conversations/          # 严格按人格隔离的会话服务
│       ├── documents/              # 上传、后台导入任务和文档生命周期
│       ├── retrieval/              # Qdrant 索引、检索和加权 RRF
│       ├── providers/              # API 配置、Fernet 加密和地址校验
│       ├── ai/                     # 模型、Embedding、加载器与提示词
│       ├── db/                     # SQLAlchemy 模型、会话与种子
│       ├── routers/                # FastAPI 路由
│       └── cli/                    # 导入、重建、清理和旧配置迁移命令
└── frontend/
    ├── package.json
    ├── vite.config.ts              # 代理 /api → localhost:8000
    └── src/
        ├── App.tsx                 # /chat、/knowledge、/settings 路由壳
        ├── api/                    # HTTP、SSE 与 Query Client
        ├── features/chat/          # 消息、输入框、引用与聊天状态
        ├── features/knowledge/     # 上传、筛选、状态与向量删除
        ├── hooks/                  # 人格、会话、上传与 Provider 状态
        ├── components/             # 侧边栏、人格管理、API 配置等
        └── types/api.ts
```

---

## 🚀 快速开始

### 0. 准备环境

需要 Python 3.10+、Node.js 18+、npm，以及可运行 Qdrant 的 Docker。推荐使用独立 Python 环境：

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

PowerShell 可用 `Copy-Item .env.example backend/.env` 代替 `cp`。

编辑 `backend/.env`，至少填入一个对话模型的 API key，并生成一个用于加密网页保存凭据的 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

DeepSeek 示例：

```dotenv
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.deepseek.com/v1
DEFAULT_GENERATION_MODEL=deepseek-v4-pro
DEFAULT_EMBEDDING_PROVIDER=huggingface
DEFAULT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
HUGGINGFACE_ENDPOINT=https://hf-mirror.com
PROVIDER_ENCRYPTION_KEY=粘贴上一步生成的Fernet密钥
```

> `.env` 是首次种子；在「API 配置」页面保存后写入 SQLite `provider_configs`，之后以数据库为准。请长期保管同一个 `PROVIDER_ENCRYPTION_KEY`，更换或丢失后将无法解密已经保存的 API key。

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

CLI 与网页上传均支持 `.txt`、`.md`、`.pdf` 和 `.docx`。原文件及任务状态写入本地持久化层，在「知识库」页可以按范围/状态筛选、重试失败任务，或通过行内确认删除文档及其向量。

### 5. 启动前端

```bash
cd ../frontend
npm install
npm run dev          # http://localhost:5173
```

打开页面 → 在顶部选择人格 → 在侧边栏点「API 配置」填好 base_url / key / 模型 → 保存（可点「测试连接」）→ 回到对话即可聊天。需要新增或修改人格时，使用侧边栏底部的「人格管理」。

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
- **地址限制**：仅支持 HTTP(S)；本机回环模型服务可直接使用，局域网地址需显式设置 `ALLOW_PRIVATE_PROVIDER_URLS=true`。此开关会放宽内网访问限制，只应在可信本地环境启用。
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

### 新增人格（无需写代码）

1. 打开网页侧边栏底部的「人格管理」。
2. 点击「创建新人格」，填写名称、简介、System Prompt；头像为可选项。
3. 如有需要，展开高级设置配置聊天模型和私有/公共知识库检索权重。
4. 保存后立即出现在聊天页顶部的人格选择器中，无需重启。

人格采用归档而非物理删除：归档后会话和私有知识库保持不变，恢复后可继续使用。系统级「通用助手」始终可用，只检索公共知识库；因此用户创建的人格可以全部归档。

### 切换模型

- **对话模型**：在「API 配置」页面改；或给单个身份在 YAML 里设 `generation_model` 覆盖模型名。
- **向量模型**：在「API 配置」页面改（切维度需重新导入）。
- **换向量库**：只有 `ai/vectorstore.py` 封装了 `QdrantVectorStore`，换个 LangChain `VectorStore` 实现即可。

### 对话数据流

`chatmaster/chat/graph.py` 中的 `StateGraph` 依次执行：

```text
load_identity → load_history → retrieve_context → build_messages
```

随后 `chatmaster/chat/service.py` 流式调用模型、发送 SSE 事件，并在会话存在时持久化用户消息、部分/完整回答和引用来源。

---

## 📡 API 一览

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查：当前 provider 配置、集合、身份 |
| GET | `/api/identities` | 身份列表（不含 system prompt） |
| GET | `/api/identities/{id}` | 单个身份详情 |
| POST | `/api/identities` | 创建人格 |
| PUT | `/api/identities/{id}` | 修改人格 |
| POST | `/api/identities/{id}/archive` | 归档人格 |
| POST | `/api/identities/{id}/restore` | 恢复人格 |
| POST | `/api/identities/{id}/duplicate` | 复制人格 |
| POST | `/api/chat` | SSE 流式对话 |
| POST | `/api/conversations` | 创建会话 |
| GET | `/api/conversations` | 会话列表 |
| GET | `/api/conversations/{id}/messages` | 会话消息 |
| PUT | `/api/conversations/{id}` | 重命名会话 |
| DELETE | `/api/conversations/{id}` | 删除会话 |
| GET | `/api/documents` | 文档列表（支持范围/状态筛选） |
| GET | `/api/documents/{id}` | 文档详情 |
| POST | `/api/documents/ingest` | 提交后台文档导入任务（202） |
| GET | `/api/ingest-jobs` | 导入任务列表 |
| GET | `/api/ingest-jobs/{id}` | 导入任务详情 |
| POST | `/api/ingest-jobs/{id}/retry` | 重试失败导入 |
| DELETE | `/api/documents/{id}` | 删除文件、分块与向量 |
| GET | `/api/indexes` | 索引版本和新鲜度 |
| POST | `/api/indexes/rebuild` | 后台重建索引 |
| GET | `/api/providers` | 读取 API 配置（key 脱敏） |
| PUT | `/api/providers` | 保存 API 配置 |
| POST | `/api/providers/test` | 测试对话 + 向量连接 |

---

## 🔧 开发提示

- **运行后端测试**：在 `backend/` 执行 `pytest`，静态检查执行 `ruff check .`。
- **运行前端检查**：在 `frontend/` 执行 `npm test` 和 `npm run build`。
- **本地安全边界**：当前 `LOCAL_WORKSPACE_ID` / `LOCAL_USER_ID` 是未来认证的替换点，不是登录系统；只应在受信网络中运行。
- **Qdrant 版本警告**：客户端版本与 server 版本不一致会打印 `UserWarning`，功能不受影响。如需消除，把 `docker-compose.yml` 的 Qdrant 镜像升到与 `qdrant-client` minor 相近的版本。
- **代理 / TUN 的 Fake IP**：如果公共 Provider 域名被代理解析到保留或私有地址，后端的出站地址校验会拒绝请求。优先让该域名走真实 DNS；仅在可信本地环境下考虑启用 `ALLOW_PRIVATE_PROVIDER_URLS=true`。
- **Starlette 路由校验**：`include_router` 产生的是惰性 `_IncludedRouter`，不要靠遍历 `app.routes` 校验路由是否注册——直接用 httpx `ASGITransport` 打请求验证。
- **Windows npm 缓存权限**：若全局缓存目录 EPERM，用 `npm install --cache /tmp/npm-cache`。
- **HuggingFace 镜像**：必须在导入任何 `huggingface_hub` 相关库**之前**设 `HF_ENDPOINT`，否则镜像不生效（已在 `main.py` / `cli/ingest.py` 顶部默认设为 `https://hf-mirror.com`）。

---

## 📦 开发依赖

dev 附加项（`pip install -e ".[dev]"`）：`pytest`、`pytest-asyncio`、`httpx`、`ruff`。

## 📄 License

MIT
