import { useEffect, useRef } from "react";
import type { Message } from "../../types/api";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: Message[];
  isStreaming: boolean;
}

export function ChatWindow({ messages, isStreaming }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-hint">选择一个身份，开始对话吧。</div>
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
