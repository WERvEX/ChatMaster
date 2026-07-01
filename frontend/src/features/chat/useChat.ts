import { useCallback, useEffect, useRef, useState } from "react";
import { createConversation, getConversationMessages } from "../../api/client";
import { streamChat } from "../../api/sse";
import type { Message, SourceItem } from "../../types/api";

interface Options {
  conversationId: string | null;
  onConversationId: (id: string) => void;
}

export function useChat(identityId: string | null, options: Options) {
  const { conversationId, onConversationId } = options;
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      setSources([]);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    setError(null);
    getConversationMessages(conversationId)
      .then((items) => {
        if (cancelled) return;
        setMessages(
          items.map((item) => ({
            role: item.role as Message["role"],
            content: item.content,
          }))
        );
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!identityId || !text.trim() || isStreaming) return;

      let activeConversationId = conversationId;
      if (!activeConversationId) {
        try {
          const created = await createConversation(identityId, text.slice(0, 30));
          activeConversationId = created.id;
          onConversationId(created.id);
        } catch (e) {
          setError(String(e));
          return;
        }
      }

      const userMsg: Message = { role: "user", content: text };
      setMessages((m) => [...m, userMsg]);
      setSources([]);
      setError(null);
      setIsStreaming(true);

      let buffer = "";
      setMessages((m) => [...m, { role: "assistant", content: "" }]);

      const ctrl = streamChat(
        {
          identity_id: identityId,
          message: text,
          history: [],
          conversation_id: activeConversationId,
        },
        {
          onSources: (s) => setSources(s),
          onToken: (delta) => {
            buffer += delta;
            setMessages((m) => {
              const next = [...m];
              next[next.length - 1] = { role: "assistant", content: buffer };
              return next;
            });
          },
          onDone: (payload) => {
            setIsStreaming(false);
            if (payload.conversation_id && payload.conversation_id !== conversationId) {
              onConversationId(payload.conversation_id);
            }
          },
          onError: (detail) => {
            setError(detail);
            setIsStreaming(false);
            setMessages((m) => {
              if (
                m.length &&
                m[m.length - 1].role === "assistant" &&
                m[m.length - 1].content === ""
              ) {
                return m.slice(0, -1);
              }
              return m;
            });
          },
        }
      );
      ctrlRef.current = ctrl;
    },
    [conversationId, identityId, isStreaming, onConversationId]
  );

  const stop = useCallback(() => {
    ctrlRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return {
    messages,
    isStreaming,
    sources,
    error,
    loadingHistory,
    sendMessage,
    stop,
  };
}
