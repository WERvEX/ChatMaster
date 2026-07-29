import { useEffect, useRef } from "react";
import type { Message } from "../../types/api";
import type { IdentityOut } from "../../types/api";
import { Avatar } from "../../components/Avatar";
import { ChatMessage } from "./ChatMessage";

interface Props {
  messages: Message[];
  isStreaming: boolean;
  emptyText: string;
  identity?: IdentityOut | null;
}

export function ChatWindow({ messages, isStreaming, emptyText, identity }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-hint">
          <Avatar identity={identity} size="lg" />
          <h1>{emptyText}</h1>
          <p>{identity?.description || "发送一条消息，开始新的对话。"}</p>
        </div>
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
