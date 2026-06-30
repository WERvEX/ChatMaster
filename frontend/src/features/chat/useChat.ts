import { useCallback, useRef, useState } from "react";
import { streamChat } from "../../api/sse";
import type { Message, SourceItem } from "../../types/api";

export function useChat(identityId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const ctrlRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    (text: string) => {
      if (!identityId || !text.trim() || isStreaming) return;

      const history = messages;
      const userMsg: Message = { role: "user", content: text };
      setMessages((m) => [...m, userMsg]);
      setSources([]);
      setError(null);
      setIsStreaming(true);

      // Streaming assistant buffer — committed to messages on done.
      let buffer = "";
      setMessages((m) => [...m, { role: "assistant", content: "" }]);

      const ctrl = streamChat(
        { identity_id: identityId, message: text, history },
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
          onDone: () => {
            setIsStreaming(false);
          },
          onError: (detail) => {
            setError(detail);
            setIsStreaming(false);
            // Remove the empty assistant placeholder if nothing streamed.
            setMessages((m) => {
              if (m.length && m[m.length - 1].role === "assistant" && m[m.length - 1].content === "") {
                return m.slice(0, -1);
              }
              return m;
            });
          },
        }
      );
      ctrlRef.current = ctrl;
    },
    [identityId, isStreaming, messages]
  );

  const stop = useCallback(() => {
    ctrlRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    setSources([]);
    setError(null);
  }, []);

  return { messages, isStreaming, sources, error, sendMessage, stop, clear };
}
