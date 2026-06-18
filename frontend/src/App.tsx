import { useEffect, useState } from "react";
import { useIdentities } from "./hooks/useIdentities";
import { useChat } from "./hooks/useChat";
import { IdentitySelector } from "./components/IdentitySelector";
import { ChatWindow } from "./components/ChatWindow";
import { ChatInput } from "./components/ChatInput";
import { SourceList } from "./components/SourceList";
import { DocumentUpload } from "./components/DocumentUpload";
import { ProviderSettings } from "./components/ProviderSettings";

type View = "chat" | "settings";

export default function App() {
  const { identities, loading, error } = useIdentities();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("chat");
  const chat = useChat(selectedId);

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
            setView("chat");
          }}
          loading={loading}
          error={error}
        />
        {selectedId && view === "chat" && <DocumentUpload identityId={selectedId} />}
        <button
          className={`settings-toggle ${view === "settings" ? "active" : ""}`}
          onClick={() => setView(view === "settings" ? "chat" : "settings")}
        >
          ⚙ API 配置
        </button>
      </aside>

      {view === "settings" ? (
        <ProviderSettings onBack={() => setView("chat")} />
      ) : (
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
      )}
    </div>
  );
}
