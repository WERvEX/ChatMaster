import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useIdentities } from "./hooks/useIdentities";
import { useConversations } from "./hooks/useConversations";
import { useChat } from "./features/chat/useChat";
import { IdentitySelector } from "./components/IdentitySelector";
import { ChatWindow } from "./features/chat/ChatWindow";
import { ChatInput } from "./features/chat/ChatInput";
import { ProviderSettings } from "./components/ProviderSettings";
import { KnowledgePage } from "./features/knowledge/KnowledgePage";

function formatWhen(iso: string) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

export default function App() {
  const { identities, loading, error } = useIdentities();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const conversations = useConversations(selectedId);
  const chat = useChat(selectedId, {
    conversationId: conversations.activeId,
    onConversationId: (id) => {
      conversations.setActiveId(id);
      if (selectedId) {
        void conversations.refresh();
      }
    },
  });
  const isChatRoute = location.pathname === "/chat";
  const isSettingsRoute = location.pathname === "/settings";
  const isKnowledgeRoute = location.pathname === "/knowledge";

  useEffect(() => {
    if (!loading && identities.length > 0 && !selectedId) {
      setSelectedId(identities[0].id);
    }
  }, [identities, loading, selectedId]);

  return (
    <div className="app">
      <aside className="sidebar">
        <h1 className="brand">ChatMaster</h1>
        <IdentitySelector
          identities={identities}
          selectedId={selectedId}
          onSelect={(id) => {
            setSelectedId(id);
            navigate("/chat");
          }}
          loading={loading}
          error={error}
        />
        {selectedId && (
          <section className="conversation-panel">
            <div className="conversation-panel-header">
              <span>会话</span>
              <button
                className="btn-link"
                type="button"
                onClick={() => conversations.setActiveId(null)}
              >
                新建
              </button>
            </div>
            {conversations.loading && <div className="muted">加载会话…</div>}
            {conversations.error && <div className="error">{conversations.error}</div>}
            <ul className="conversation-list">
              {conversations.conversations.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`conversation-item ${
                      conversations.activeId === item.id ? "active" : ""
                    }`}
                    onClick={() => conversations.selectConversation(item.id)}
                  >
                    <span className="conversation-title">{item.title}</span>
                    <span className="conversation-time">{formatWhen(item.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
        <nav className="sidebar-nav" aria-label="主导航">
          <button
            className={`settings-toggle ${isChatRoute ? "active" : ""}`}
            onClick={() => navigate("/chat")}
          >
            对话
          </button>
          <button
            className={`settings-toggle ${isKnowledgeRoute ? "active" : ""}`}
            onClick={() => navigate("/knowledge")}
          >
            知识库
          </button>
          <button
            className={`settings-toggle ${isSettingsRoute ? "active" : ""}`}
            onClick={() => navigate("/settings")}
          >
            API 配置
          </button>
        </nav>
      </aside>

      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/settings" element={<ProviderSettings onBack={() => navigate("/chat")} />} />
        <Route
          path="/knowledge"
          element={<KnowledgePage identityId={selectedId} onBack={() => navigate("/chat")} />}
        />
        <Route
          path="/chat"
          element={
            <main className="main">
              <div className="main-header">
                <span>{identities.find((i) => i.id === selectedId)?.name ?? "未选择身份"}</span>
                {selectedId && conversations.activeId && (
                  <button
                    className="btn-link danger-link"
                    type="button"
                    onClick={() => {
                      if (window.confirm("确定删除当前会话及其全部消息吗？此操作无法撤销。")) {
                        void conversations.deleteActiveConversation();
                      }
                    }}
                  >
                    删除会话
                  </button>
                )}
              </div>
              {chat.loadingHistory && <div className="muted">加载历史…</div>}
              <ChatWindow
                messages={chat.messages}
                isStreaming={chat.isStreaming}
                emptyText={selectedId ? "发送一条消息开始对话。" : "请先选择一个身份。"}
              />
              {chat.error && <div className="error">{chat.error}</div>}
              <ChatInput
                onSend={(text) => void chat.sendMessage(text)}
                onStop={chat.stop}
                isStreaming={chat.isStreaming}
                disabled={!selectedId || chat.loadingHistory}
              />
            </main>
          }
        />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </div>
  );
}
