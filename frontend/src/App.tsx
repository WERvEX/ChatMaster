import { Menu } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ConversationSidebar } from "./components/ConversationSidebar";
import { PersonaManager } from "./components/PersonaManager";
import { PersonaSelector } from "./components/PersonaSelector";
import { ProviderSettings } from "./components/ProviderSettings";
import { ChatInput } from "./features/chat/ChatInput";
import { ChatWindow } from "./features/chat/ChatWindow";
import { useChat } from "./features/chat/useChat";
import { KnowledgePage } from "./features/knowledge/KnowledgePage";
import { useConversations } from "./hooks/useConversations";
import { useIdentities } from "./hooks/useIdentities";
import type { IdentityDetail, IdentityPayload } from "./types/api";

const SELECTED_IDENTITY_KEY = "chatmaster:selected-identity";

export default function App() {
  const identityStore = useIdentities();
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(SELECTED_IDENTITY_KEY);
    } catch {
      return null;
    }
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [personaManager, setPersonaManager] = useState<"list" | "create" | null>(null);
  const autoCreatingRef = useRef(false);
  const location = useLocation();
  const navigate = useNavigate();

  const activeIdentities = useMemo(
    () => identityStore.identities.filter((item) => !item.is_archived),
    [identityStore.identities]
  );
  const selectedIdentity =
    activeIdentities.find((item) => item.id === selectedId) ??
    activeIdentities.find((item) => item.is_system) ??
    activeIdentities[0] ??
    null;

  useEffect(() => {
    if (identityStore.loading || !selectedIdentity) return;
    if (selectedIdentity.id !== selectedId) setSelectedId(selectedIdentity.id);
  }, [identityStore.loading, selectedId, selectedIdentity]);

  useEffect(() => {
    if (!selectedId) return;
    try {
      localStorage.setItem(SELECTED_IDENTITY_KEY, selectedId);
    } catch {
      // Device-local preference only; private browsing can reject writes.
    }
  }, [selectedId]);

  const conversations = useConversations(selectedId);
  const chat = useChat(selectedId, {
    conversationId: conversations.activeId,
    onConversationId: (id) => {
      conversations.setActiveId(id);
      void conversations.refresh();
    },
    onTurnDone: () => void conversations.refresh(),
  });

  useEffect(() => {
    if (
      !selectedId ||
      conversations.loading ||
      conversations.conversations.length > 0 ||
      conversations.activeId ||
      autoCreatingRef.current
    ) {
      return;
    }
    autoCreatingRef.current = true;
    void conversations.startConversation().finally(() => {
      autoCreatingRef.current = false;
    });
  }, [
    conversations.activeId,
    conversations.conversations.length,
    conversations.loading,
    conversations.startConversation,
    selectedId,
  ]);

  const activeRoute = location.pathname === "/knowledge"
    ? "knowledge"
    : location.pathname === "/settings"
      ? "settings"
      : "chat";

  const go = (route: "chat" | "knowledge" | "settings") => {
    navigate(`/${route}`);
    setMobileSidebarOpen(false);
  };

  const createPersona = async (payload: IdentityPayload) => {
    const created = await identityStore.create(payload) as IdentityDetail;
    setSelectedId(created.id);
    setPersonaManager(null);
    navigate("/chat");
    return created;
  };

  return (
    <div className="app-shell">
      <ConversationSidebar
        conversations={conversations.conversations}
        activeId={conversations.activeId}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        activeRoute={activeRoute}
        onToggle={() => {
          if (window.matchMedia("(max-width: 760px)").matches) {
            setMobileSidebarOpen(false);
          } else {
            setSidebarCollapsed((value) => !value);
          }
        }}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onSelect={(id) => {
          conversations.selectConversation(id);
          navigate("/chat");
          setMobileSidebarOpen(false);
        }}
        onCreate={() => {
          void conversations.startConversation();
          navigate("/chat");
          setMobileSidebarOpen(false);
        }}
        onRename={conversations.renameConversation}
        onDelete={conversations.removeConversation}
        onNavigate={go}
        onManagePersonas={() => setPersonaManager("list")}
      />

      <div className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route
            path="/chat"
            element={
              <main className="chat-page">
                <header className="chat-header">
                  <button className="mobile-menu-button" type="button" onClick={() => setMobileSidebarOpen(true)} aria-label="打开侧边栏">
                    <Menu size={20} />
                  </button>
                  <PersonaSelector
                    identities={activeIdentities}
                    selectedId={selectedId}
                    disabled={chat.isStreaming}
                    onSelect={(id) => {
                      setSelectedId(id);
                      navigate("/chat");
                    }}
                    onCreate={() => setPersonaManager("create")}
                    onManage={() => setPersonaManager("list")}
                  />
                  <span className="header-status">
                    {chat.isStreaming ? "正在回复…" : selectedIdentity?.description}
                  </span>
                </header>
                {chat.loadingHistory && <div className="page-notice">正在加载对话…</div>}
                <ChatWindow
                  messages={chat.messages}
                  isStreaming={chat.isStreaming}
                  emptyText="今天想聊点什么？"
                  identity={selectedIdentity}
                />
                {chat.error && <div className="page-error">{chat.error}</div>}
                <ChatInput
                  onSend={(text) => void chat.sendMessage(text)}
                  onStop={chat.stop}
                  isStreaming={chat.isStreaming}
                  disabled={!selectedId || chat.loadingHistory}
                  identityName={selectedIdentity?.name}
                />
              </main>
            }
          />
          <Route path="/settings" element={<ProviderSettings onBack={() => navigate("/chat")} />} />
          <Route path="/knowledge" element={<KnowledgePage identityId={selectedId} onBack={() => navigate("/chat")} />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </div>

      <PersonaManager
        open={personaManager !== null}
        initialMode={personaManager === "create" ? "create" : "list"}
        identities={identityStore.identities}
        onClose={() => setPersonaManager(null)}
        onCreate={createPersona}
        onUpdate={identityStore.update}
        onArchive={identityStore.archive}
        onRestore={identityStore.restore}
        onDuplicate={identityStore.duplicate}
      />
    </div>
  );
}
