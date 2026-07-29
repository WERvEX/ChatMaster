import { ChevronDown, Plus, Settings2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { IdentityOut } from "../types/api";
import { Avatar } from "./Avatar";

type Props = {
  identities: IdentityOut[];
  selectedId: string | null;
  disabled?: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onManage: () => void;
};

export function PersonaSelector({
  identities,
  selectedId,
  disabled,
  onSelect,
  onCreate,
  onManage,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = identities.find((item) => item.id === selectedId) ?? identities[0];

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="persona-selector" ref={ref}>
      <button
        className="persona-trigger"
        type="button"
        disabled={disabled || !selected}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Avatar identity={selected} size="sm" />
        <span>{selected?.name ?? "选择人格"}</span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="persona-menu" role="menu">
          <div className="persona-menu-label">切换人格</div>
          {identities.map((identity) => (
            <button
              key={identity.id}
              className={`persona-option ${identity.id === selectedId ? "selected" : ""}`}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(identity.id);
                setOpen(false);
              }}
            >
              <Avatar identity={identity} />
              <span>
                <strong>{identity.name}</strong>
                <small>{identity.description || "暂无简介"}</small>
              </span>
            </button>
          ))}
          <div className="persona-menu-actions">
            <button type="button" onClick={() => { setOpen(false); onCreate(); }}>
              <Plus size={16} /> 创建人格
            </button>
            <button type="button" onClick={() => { setOpen(false); onManage(); }}>
              <Settings2 size={16} /> 管理人格
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
