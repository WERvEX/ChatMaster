import { useCallback, useEffect, useRef, useState } from "react";
import { cancelChat, getConversationMessages } from "../../api/client";
import { streamChat } from "../../api/sse";
import type { Message } from "../../types/api";

interface Options {
  conversationId: string | null;
  onConversationId: (id: string) => void;
  onTurnDone?: () => void;
}

interface ActiveStream {
  key: string;
  requestId: string;
  ctrl: AbortController;
}

export function useChat(identityId: string | null, options: Options) {
  const { conversationId, onConversationId, onTurnDone } = options;
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const activeRef = useRef<ActiveStream | null>(null);
  const skipHistoryLoadFor = useRef<string | null>(null);
  const selectionRef = useRef(`${identityId ?? ""}:${conversationId ?? ""}`);
  selectionRef.current = `${identityId ?? ""}:${conversationId ?? ""}`;

  const stopActive = useCallback(async (abortAfter = true) => {
    const active = activeRef.current;
    if (!active) return;
    await cancelChat(active.requestId);
    if (abortAfter) {
      window.setTimeout(() => active.ctrl.abort(), 2000);
    }
  }, []);

  useEffect(() => {
    void stopActive(false).then(() => activeRef.current?.ctrl.abort());
    activeRef.current = null;
    setIsStreaming(false);

    if (!conversationId) {
      setMessages([]);
      setError(null);
      return;
    }
    if (skipHistoryLoadFor.current === conversationId) {
      skipHistoryLoadFor.current = null;
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
            id: item.id,
            role: item.role as Message["role"],
            content: item.content,
            request_id: item.request_id,
            status: item.status,
            sources: item.sources_json ?? [],
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
  }, [conversationId, identityId, stopActive]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!identityId || !text.trim() || isStreaming) return;
      const requestId = crypto.randomUUID();
      const selection = `${identityId}:${conversationId ?? ""}`;
      const streamKey = `${selection}:${requestId}`;
      const user: Message = {
        role: "user",
        content: text.trim(),
        request_id: requestId,
        status: "complete",
      };
      const assistant: Message = {
        role: "assistant",
        content: "",
        request_id: requestId,
        status: "pending",
        sources: [],
      };
      setMessages((items) => [...items, user, assistant]);
      setError(null);
      setIsStreaming(true);
      let buffer = "";

      const ctrl = streamChat(
        {
          request_id: requestId,
          identity_id: identityId,
          message: text.trim(),
          conversation_id: conversationId,
        },
        {
          onSources: (sources) => {
            if (activeRef.current?.key !== streamKey || selectionRef.current !== selection) return;
            setMessages((items) =>
              items.map((item) =>
                item.request_id === requestId && item.role === "assistant"
                  ? { ...item, sources }
                  : item
              )
            );
          },
          onToken: (delta) => {
            if (activeRef.current?.key !== streamKey || selectionRef.current !== selection) return;
            buffer += delta;
            setMessages((items) =>
              items.map((item) =>
                item.request_id === requestId && item.role === "assistant"
                  ? { ...item, content: buffer }
                  : item
              )
            );
          },
          onDone: (payload) => {
            if (activeRef.current?.key !== streamKey) return;
            activeRef.current = null;
            setIsStreaming(false);
            setMessages((items) =>
              items.map((item) =>
                item.request_id === requestId && item.role === "assistant"
                  ? { ...item, id: payload.message_id, status: payload.status }
                  : item
              )
            );
            if (payload.conversation_id && !conversationId) {
              skipHistoryLoadFor.current = payload.conversation_id;
              onConversationId(payload.conversation_id);
            }
            onTurnDone?.();
          },
          onError: (detail) => {
            if (activeRef.current?.key !== streamKey) return;
            activeRef.current = null;
            setError(detail);
            setIsStreaming(false);
            setMessages((items) =>
              items.map((item) =>
                item.request_id === requestId && item.role === "assistant"
                  ? { ...item, status: "failed" }
                  : item
              )
            );
          },
        }
      );
      activeRef.current = { key: streamKey, requestId, ctrl };
    },
    [conversationId, identityId, isStreaming, onConversationId, onTurnDone]
  );

  const stop = useCallback(() => {
    void stopActive(true);
  }, [stopActive]);

  return { messages, isStreaming, error, loadingHistory, sendMessage, stop };
}
