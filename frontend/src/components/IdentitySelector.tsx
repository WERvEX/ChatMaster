import type { IdentityOut } from "../types/api";

interface Props {
  identities: IdentityOut[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  error: string | null;
}

export function IdentitySelector({ identities, selectedId, onSelect, loading, error }: Props) {
  if (loading) return <div className="muted">加载身份中…</div>;
  if (error) return <div className="error">身份加载失败: {error}</div>;

  return (
    <div className="identity-list">
      {identities.map((it) => (
        <button
          key={it.id}
          className={`identity-card ${selectedId === it.id ? "active" : ""}`}
          onClick={() => onSelect(it.id)}
        >
          <div className="identity-name">{it.name}</div>
          <div className="identity-desc">{it.description}</div>
        </button>
      ))}
    </div>
  );
}
