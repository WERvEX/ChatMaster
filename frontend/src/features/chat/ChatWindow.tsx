import { useEffect, useRef } from "react";
import type { Message } from "../../types/api";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: Message[];
  isStreaming: boolean;
  emptyText: string;
}

export function ChatWindow({ messages, isStreaming, emptyText }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-hint">{emptyText}</div>
      )}
      {messages.map((m, i) => (
        <ChatMessage key={i} msg={m} />
      ))}
      {isStreaming && messages.length > 0 && (
        <div className="typing">● ● ●</div>
      )}
      <div ref={endRef} />
    </div>
  );
}
