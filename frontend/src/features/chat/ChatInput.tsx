import { useState } from "react";

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
  identityName?: string;
}

export function ChatInput({ onSend, onStop, isStreaming, disabled, identityName }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  return (
    <div className="composer-shell">
      <div className="chat-input">
        <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder={disabled ? "请先选择一个人格" : `给${identityName ?? "助手"}发送消息`}
        disabled={disabled}
        rows={2}
        />
        {isStreaming ? (
          <button className="btn-stop" onClick={onStop} aria-label="停止生成">■</button>
        ) : (
          <button className="btn-send" onClick={submit} disabled={disabled || !text.trim()} aria-label="发送消息">
            ↑
          </button>
        )}
      </div>
      <p>AI 可能会犯错，请核对重要信息。</p>
    </div>
  );
}
