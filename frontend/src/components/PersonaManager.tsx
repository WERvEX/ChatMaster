import {
  Archive,
  Copy,
  Pencil,
  Plus,
  RotateCcw,
  SlidersHorizontal,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getIdentity } from "../api/client";
import type { IdentityOut, IdentityPayload } from "../types/api";
import { Avatar } from "./Avatar";

const emptyPayload: IdentityPayload = {
  name: "",
  description: "",
  system_prompt: "你是一位可靠、清晰、友善的 AI 助手。",
  avatar_url: null,
  generation_model: null,
  embedding_model: null,
  retrieval: {
    top_k: 6,
    private_weight: 0.6,
    common_weight: 0.4,
    min_chunks_common: 2,
  },
};

async function fileToAvatar(file: File): Promise<string> {
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
    throw new Error("请选择 PNG、JPG 或 WebP 图片");
  }
  if (file.size > 2 * 1024 * 1024) throw new Error("头像不能超过 2MB");
  const src = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = src;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 256;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("无法处理头像");
    const side = Math.min(image.width, image.height);
    const sx = (image.width - side) / 2;
    const sy = (image.height - side) / 2;
    context.drawImage(image, sx, sy, side, side, 0, 0, 256, 256);
    return canvas.toDataURL("image/webp", 0.86);
  } finally {
    URL.revokeObjectURL(src);
  }
}

type Props = {
  open: boolean;
  initialMode?: "list" | "create";
  identities: IdentityOut[];
  onClose: () => void;
  onCreate: (payload: IdentityPayload) => Promise<unknown>;
  onUpdate: (id: string, payload: IdentityPayload) => Promise<unknown>;
  onArchive: (id: string) => Promise<unknown>;
  onRestore: (id: string) => Promise<unknown>;
  onDuplicate: (id: string) => Promise<unknown>;
};

export function PersonaManager(props: Props) {
  const [mode, setMode] = useState<"list" | "form">("list");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [payload, setPayload] = useState<IdentityPayload>(emptyPayload);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!props.open) return;
    setMode(props.initialMode === "create" ? "form" : "list");
    setEditingId(null);
    setPayload(emptyPayload);
    setError(null);
  }, [props.open, props.initialMode]);

  if (!props.open) return null;

  const edit = async (id: string) => {
    setBusy(true);
    setError(null);
    try {
      const identity = await getIdentity(id);
      setPayload({
        name: identity.name,
        description: identity.description,
        system_prompt: identity.system_prompt,
        avatar_url: identity.avatar_url,
        generation_model: identity.generation_model,
        embedding_model: identity.embedding_model,
        retrieval: identity.retrieval,
      });
      setEditingId(id);
      setMode("form");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!payload.name.trim() || !payload.system_prompt.trim()) {
      setError("名称和 System Prompt 不能为空");
      return;
    }
    await act(async () => {
      if (editingId) await props.onUpdate(editingId, payload);
      else await props.onCreate(payload);
      setMode("list");
      setEditingId(null);
      setPayload(emptyPayload);
    });
  };

  const active = props.identities.filter((item) => !item.is_archived);
  const archived = props.identities.filter((item) => item.is_archived);

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="persona-manager" role="dialog" aria-modal="true" aria-label="人格管理">
        <header>
          <div>
            <h2>{mode === "form" ? (editingId ? "编辑人格" : "创建人格") : "人格管理"}</h2>
            <p>{mode === "form" ? "设置它的表达方式与知识检索偏好。" : "创建、复制、归档或恢复你的专属助手。"}</p>
          </div>
          <button className="icon-button" type="button" onClick={props.onClose} aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        {error && <div className="modal-error">{error}</div>}

        {mode === "list" ? (
          <div className="persona-manager-body">
            <button className="create-persona-card" type="button" onClick={() => { setEditingId(null); setPayload(emptyPayload); setMode("form"); }}>
              <Plus size={20} />
              <span><strong>创建新人格</strong><small>从一个干净的配置开始</small></span>
            </button>
            <h3>启用中</h3>
            <div className="persona-admin-list">
              {active.map((identity) => (
                <div className="persona-admin-row" key={identity.id}>
                  <Avatar identity={identity} />
                  <span className="persona-admin-copy">
                    <strong>{identity.name}{identity.is_system && <em>系统</em>}</strong>
                    <small>{identity.description}</small>
                  </span>
                  {!identity.is_system && (
                    <span className="persona-admin-actions">
                      <button type="button" title="编辑" onClick={() => void edit(identity.id)}><Pencil size={16} /></button>
                      <button type="button" title="复制" onClick={() => void act(() => props.onDuplicate(identity.id))}><Copy size={16} /></button>
                      <button type="button" title="归档" onClick={() => void act(() => props.onArchive(identity.id))}><Archive size={16} /></button>
                    </span>
                  )}
                </div>
              ))}
            </div>
            {archived.length > 0 && (
              <>
                <h3>已归档</h3>
                <div className="persona-admin-list archived">
                  {archived.map((identity) => (
                    <div className="persona-admin-row" key={identity.id}>
                      <Avatar identity={identity} />
                      <span className="persona-admin-copy"><strong>{identity.name}</strong><small>{identity.description}</small></span>
                      <button className="restore-button" type="button" onClick={() => void act(() => props.onRestore(identity.id))}>
                        <RotateCcw size={15} /> 恢复
                      </button>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="persona-form">
            <div className="avatar-editor">
              <Avatar identity={{ name: payload.name || "新人格", avatar_url: payload.avatar_url }} size="lg" />
              <label className="secondary-button">
                <Upload size={16} /> 选择头像
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void fileToAvatar(file).then((avatar_url) => setPayload((value) => ({ ...value, avatar_url }))).catch((reason) => setError(String(reason)));
                  }}
                />
              </label>
              {payload.avatar_url && <button className="text-button" type="button" onClick={() => setPayload((value) => ({ ...value, avatar_url: null }))}>使用默认头像</button>}
            </div>
            <label><span>名称</span><input value={payload.name} maxLength={255} onChange={(event) => setPayload((value) => ({ ...value, name: event.target.value }))} placeholder="例如：产品策略顾问" /></label>
            <label><span>简介</span><input value={payload.description} maxLength={2000} onChange={(event) => setPayload((value) => ({ ...value, description: event.target.value }))} placeholder="一句话介绍它擅长什么" /></label>
            <label><span>System Prompt</span><textarea rows={8} value={payload.system_prompt} onChange={(event) => setPayload((value) => ({ ...value, system_prompt: event.target.value }))} /></label>
            <button className="advanced-toggle" type="button" onClick={() => setAdvanced((value) => !value)}>
              <SlidersHorizontal size={16} /> 高级设置
            </button>
            {advanced && (
              <div className="advanced-fields">
                <label><span>聊天模型（留空使用全局配置）</span><input value={payload.generation_model ?? ""} onChange={(event) => setPayload((value) => ({ ...value, generation_model: event.target.value || null }))} /></label>
                <label><span>检索数量</span><input type="number" min={1} max={20} value={payload.retrieval.top_k} onChange={(event) => setPayload((value) => ({ ...value, retrieval: { ...value.retrieval, top_k: Number(event.target.value) } }))} /></label>
                <div className="weight-grid">
                  <label><span>私有知识权重</span><input type="number" min={0} max={1} step={0.1} value={payload.retrieval.private_weight} onChange={(event) => setPayload((value) => ({ ...value, retrieval: { ...value.retrieval, private_weight: Number(event.target.value) } }))} /></label>
                  <label><span>公共知识权重</span><input type="number" min={0} max={1} step={0.1} value={payload.retrieval.common_weight} onChange={(event) => setPayload((value) => ({ ...value, retrieval: { ...value.retrieval, common_weight: Number(event.target.value) } }))} /></label>
                </div>
              </div>
            )}
            <footer>
              <button className="secondary-button" type="button" onClick={() => setMode("list")}>返回</button>
              <button className="primary-button" type="button" disabled={busy} onClick={() => void save()}>{busy ? "保存中…" : "保存人格"}</button>
            </footer>
          </div>
        )}
        {busy && mode === "list" && <div className="modal-busy">处理中…</div>}
      </section>
    </div>
  );
}
