import type { Message } from "../../types/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SourceList } from "./SourceList";

export function ChatMessage({ msg }: { msg: Message }) {
  const anchorPrefix = `message-${msg.id ?? msg.request_id ?? "draft"}`;
  const markdown = msg.content.replace(
    /\[(\d+)\]/g,
    (_match, number) => `[${number}](#${anchorPrefix}-source-${number})`
  );
  return (
    <div className={`message ${msg.role}`}>
      <div className="role-tag">{msg.role === "user" ? "我" : "助手"}</div>
      <div className="message-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
          {markdown || "…"}
        </ReactMarkdown>
        {msg.status === "stopped" && <div className="muted">已停止生成</div>}
        {msg.status === "failed" && <div className="error">生成失败</div>}
        <SourceList sources={msg.sources ?? []} anchorPrefix={anchorPrefix} />
      </div>
    </div>
  );
}
