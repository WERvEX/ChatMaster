import { useProviders } from "../hooks/useProviders";

interface Props {
  onBack: () => void;
}

const CHAT_PROVIDERS = [
  { value: "openai", label: "OpenAI 兼容 (DeepSeek / OpenAI / Moonshot …)" },
  { value: "anthropic", label: "Anthropic (Claude)" },
];

const EMBEDDING_PROVIDERS = [
  { value: "huggingface", label: "HuggingFace 本地 (免费，无需 key)" },
  { value: "openai", label: "OpenAI 兼容" },
];

export function ProviderSettings({ onBack }: Props) {
  const { config, loading, saving, testing, error, testResult, dirty, update, save, test } =
    useProviders();

  if (loading) return <div className="muted">加载 API 配置中…</div>;

  const setChat = (patch: Partial<typeof config.chat>) =>
    update({ ...config, chat: { ...config.chat, ...patch } });
  const setEmb = (patch: Partial<typeof config.embedding>) =>
    update({ ...config, embedding: { ...config.embedding, ...patch } });

  const isHf = config.embedding.provider === "huggingface";
  const isAnthropic = config.chat.provider === "anthropic";

  return (
    <div className="settings">
      <div className="main-header">
        <span>API 配置</span>
        <button className="btn-link" onClick={onBack}>返回对话</button>
      </div>

      <div className="settings-body">
        {error && <div className="error">{error}</div>}

        {/* Chat provider */}
        <section className="settings-section">
          <h3>对话模型 (Chat)</h3>
          <label className="field">
            <span>提供商</span>
            <select
              value={config.chat.provider}
              onChange={(e) => setChat({ provider: e.target.value })}
            >
              {CHAT_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          {!isAnthropic && (
            <label className="field">
              <span>Base URL</span>
              <input
                type="text"
                placeholder="https://api.deepseek.com/v1"
                value={config.chat.base_url ?? ""}
                onChange={(e) => setChat({ base_url: e.target.value || null })}
              />
            </label>
          )}
          <label className="field">
            <span>API Key</span>
            <input
              type="password"
              placeholder="sk-..."
              value={config.chat.api_key ?? ""}
              onChange={(e) => setChat({ api_key: e.target.value || null })}
            />
          </label>
          <label className="field">
            <span>模型</span>
            <input
              type="text"
              placeholder="deepseek-v4-pro"
              value={config.chat.model}
              onChange={(e) => setChat({ model: e.target.value })}
            />
          </label>
        </section>

        {/* Embedding provider */}
        <section className="settings-section">
          <h3>向量模型 (Embeddings)</h3>
          <label className="field">
            <span>提供商</span>
            <select
              value={config.embedding.provider}
              onChange={(e) => setEmb({ provider: e.target.value })}
            >
              {EMBEDDING_PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          {isHf ? (
            <label className="field">
              <span>HuggingFace 镜像</span>
              <input
                type="text"
                placeholder="https://hf-mirror.com"
                value={config.embedding.huggingface_endpoint ?? ""}
                onChange={(e) =>
                  setEmb({ huggingface_endpoint: e.target.value || null })
                }
              />
            </label>
          ) : (
            <>
              <label className="field">
                <span>Base URL</span>
                <input
                  type="text"
                  placeholder="https://api.openai.com/v1"
                  value={config.embedding.base_url ?? ""}
                  onChange={(e) => setEmb({ base_url: e.target.value || null })}
                />
              </label>
              <label className="field">
                <span>API Key</span>
                <input
                  type="password"
                  placeholder="sk-..."
                  value={config.embedding.api_key ?? ""}
                  onChange={(e) => setEmb({ api_key: e.target.value || null })}
                />
              </label>
            </>
          )}
          <label className="field">
            <span>模型</span>
            <input
              type="text"
              placeholder={isHf ? "BAAI/bge-small-zh-v1.5" : "text-embedding-3-small"}
              value={config.embedding.model}
              onChange={(e) => setEmb({ model: e.target.value })}
            />
          </label>
          <p className="muted hint">
            注意：切换向量模型后维度会变化，已有的知识库需要重新导入。
          </p>
        </section>

        <div className="settings-actions">
          <button className="btn-send" onClick={save} disabled={saving || !dirty}>
            {saving ? "保存中…" : "保存配置"}
          </button>
          <button className="btn-link" onClick={test} disabled={testing}>
            {testing ? "测试中…" : "测试连接"}
          </button>
          {dirty && <span className="muted">未保存的更改</span>}
        </div>

        {testResult && (
          <div className="settings-test">
            <div>
              <strong>对话模型：</strong>
              <span className={testResult.chat === "ok" ? "ok" : "bad"}>
                {testResult.chat === "ok" ? "✓ 成功" : `✗ ${testResult.chat}`}
              </span>
            </div>
            <div>
              <strong>向量模型：</strong>
              <span className={testResult.embedding.startsWith("ok") ? "ok" : "bad"}>
                {testResult.embedding.startsWith("ok")
                  ? `✓ ${testResult.embedding}`
                  : `✗ ${testResult.embedding}`}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
