import { useState } from "react";

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming, disabled }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  return (
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
        placeholder={disabled ? "请先选择一个身份" : "输入消息，Enter 发送，Shift+Enter 换行"}
        disabled={disabled}
        rows={2}
      />
      {isStreaming ? (
        <button className="btn-stop" onClick={onStop}>停止</button>
      ) : (
        <button className="btn-send" onClick={submit} disabled={disabled || !text.trim()}>
          发送
        </button>
      )}
    </div>
  );
}
