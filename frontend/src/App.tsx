import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useIdentities } from "./hooks/useIdentities";
import { useChat } from "./features/chat/useChat";
import { IdentitySelector } from "./components/IdentitySelector";
import { ChatWindow } from "./features/chat/ChatWindow";
import { ChatInput } from "./features/chat/ChatInput";
import { SourceList } from "./features/chat/SourceList";
import { DocumentUpload } from "./components/DocumentUpload";
import { ProviderSettings } from "./components/ProviderSettings";
import { KnowledgePage } from "./features/knowledge/KnowledgePage";

export default function App() {
  const { identities, loading, error } = useIdentities();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const chat = useChat(selectedId);
  const isChatRoute = location.pathname === "/chat";
  const isSettingsRoute = location.pathname === "/settings";
  const isKnowledgeRoute = location.pathname === "/knowledge";

  // Reset conversation when switching identity.
  useEffect(() => {
    chat.clear();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

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
        {selectedId && isChatRoute && <DocumentUpload identityId={selectedId} />}
        <button
          className={`settings-toggle ${isKnowledgeRoute ? "active" : ""}`}
          onClick={() => navigate("/knowledge")}
        >
          知识库
        </button>
        <button
          className={`settings-toggle ${isSettingsRoute ? "active" : ""}`}
          onClick={() => navigate(isSettingsRoute ? "/chat" : "/settings")}
        >
          ⚙ API 配置
        </button>
      </aside>

      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/settings" element={<ProviderSettings onBack={() => navigate("/chat")} />} />
        <Route path="/knowledge" element={<KnowledgePage identityId={selectedId} />} />
        <Route
          path="/chat"
          element={
            <main className="main">
              <div className="main-header">
                <span>{identities.find((i) => i.id === selectedId)?.name ?? "未选择身份"}</span>
                {selectedId && <button className="btn-link" onClick={chat.clear}>清空对话</button>}
              </div>
              <ChatWindow messages={chat.messages} isStreaming={chat.isStreaming} />
              <SourceList sources={chat.sources} />
              {chat.error && <div className="error">{chat.error}</div>}
              <ChatInput
                onSend={chat.sendMessage}
                onStop={chat.stop}
                isStreaming={chat.isStreaming}
                disabled={!selectedId}
              />
            </main>
          }
        />
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </div>
  );
}
