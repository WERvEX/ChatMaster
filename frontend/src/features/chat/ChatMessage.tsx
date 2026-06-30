import type { Message } from "../../types/api";

export function ChatMessage({ msg }: { msg: Message }) {
  return (
    <div className={`message ${msg.role}`}>
      <div className="role-tag">{msg.role === "user" ? "我" : "助手"}</div>
      <div className="message-content">{msg.content || "…"}</div>
    </div>
  );
}
