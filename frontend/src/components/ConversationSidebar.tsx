import {
  Archive,
  Check,
  Database,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Settings,
  Trash2,
  UserRoundCog,
  X,
} from "lucide-react";
import { useState } from "react";
import type { ConversationOut } from "../types/api";

type Props = {
  conversations: ConversationOut[];
  activeId: string | null;
  collapsed: boolean;
  mobileOpen: boolean;
  activeRoute: "chat" | "knowledge" | "settings";
  onToggle: () => void;
  onCloseMobile: () => void;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onNavigate: (route: "chat" | "knowledge" | "settings") => void;
  onManagePersonas: () => void;
};

export function ConversationSidebar(props: Props) {
  const [menuId, setMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [title, setTitle] = useState("");

  const submitRename = async (id: string) => {
    if (!title.trim()) return;
    await props.onRename(id, title.trim());
    setEditingId(null);
    setMenuId(null);
  };

  return (
    <>
      <aside className={`sidebar ${props.collapsed ? "collapsed" : ""} ${props.mobileOpen ? "mobile-open" : ""}`}>
        <div className="sidebar-top">
          <div className="brand-row">
            {!props.collapsed && <span className="brand">ChatMaster</span>}
            <button className="icon-button" type="button" onClick={props.onToggle} aria-label="折叠侧边栏">
              {props.collapsed ? <Menu size={19} /> : <Archive size={18} />}
            </button>
          </div>
          <button className="new-chat-button" type="button" onClick={props.onCreate}>
            <Plus size={18} />
            {!props.collapsed && <span>新建聊天</span>}
          </button>
        </div>

        <div className="conversation-scroll">
          {!props.collapsed && <div className="conversation-section-label">最近对话</div>}
          {props.conversations.map((item) => (
            <div
              className={`conversation-row ${item.id === props.activeId ? "active" : ""}`}
              key={item.id}
            >
              {editingId === item.id ? (
                <form onSubmit={(event) => { event.preventDefault(); void submitRename(item.id); }}>
                  <input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} />
                  <button type="submit" aria-label="保存"><Check size={15} /></button>
                  <button type="button" aria-label="取消" onClick={() => setEditingId(null)}><X size={15} /></button>
                </form>
              ) : deletingId === item.id ? (
                <div className="delete-confirm">
                  <span>永久删除？</span>
                  <button type="button" onClick={() => void props.onDelete(item.id)}>删除</button>
                  <button type="button" onClick={() => setDeletingId(null)}>取消</button>
                </div>
              ) : (
                <>
                  <button className="conversation-select" type="button" onClick={() => props.onSelect(item.id)}>
                    <MessageSquare size={16} />
                    {!props.collapsed && <span>{item.title}</span>}
                  </button>
                  {!props.collapsed && (
                    <div className="conversation-more">
                      <button type="button" aria-label="会话操作" onClick={() => setMenuId(menuId === item.id ? null : item.id)}>
                        <MoreHorizontal size={16} />
                      </button>
                      {menuId === item.id && (
                        <div className="conversation-popover">
                          <button type="button" onClick={() => { setEditingId(item.id); setTitle(item.title); }}>
                            <Pencil size={15} /> 重命名
                          </button>
                          <button className="danger" type="button" onClick={() => { setDeletingId(item.id); setMenuId(null); }}>
                            <Trash2 size={15} /> 删除
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        <nav className="sidebar-footer" aria-label="管理">
          <button type="button" onClick={props.onManagePersonas} title="人格管理">
            <UserRoundCog size={18} /> {!props.collapsed && <span>人格管理</span>}
          </button>
          <button className={props.activeRoute === "knowledge" ? "active" : ""} type="button" onClick={() => props.onNavigate("knowledge")} title="知识库">
            <Database size={18} /> {!props.collapsed && <span>知识库</span>}
          </button>
          <button className={props.activeRoute === "settings" ? "active" : ""} type="button" onClick={() => props.onNavigate("settings")} title="API 配置">
            <Settings size={18} /> {!props.collapsed && <span>API 配置</span>}
          </button>
        </nav>
      </aside>
      {props.mobileOpen && <button className="sidebar-backdrop" type="button" aria-label="关闭侧边栏" onClick={props.onCloseMobile} />}
    </>
  );
}
