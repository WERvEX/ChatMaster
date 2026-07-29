import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { ChatRequest, SourceItem } from "../types/api";

export interface ChatStreamCallbacks {
  onSources: (sources: SourceItem[]) => void;
  onToken: (delta: string) => void;
  onDone: (payload: {
    message_id: string;
    conversation_id?: string;
    request_id: string;
    status: "complete" | "stopped";
  }) => void;
  onError: (detail: string, code?: string) => void;
}

/**
 * Stream a chat response from POST /api/chat using fetch-event-source
 * (native EventSource is GET-only and can't carry the JSON body).
 */
export function streamChat(req: ChatRequest, cb: ChatStreamCallbacks): AbortController {
  const ctrl = new AbortController();

  void fetchEventSource("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal: ctrl.signal,
    onmessage(ev) {
      const data = ev.data ? JSON.parse(ev.data) : {};
      switch (ev.event) {
        case "sources":
          cb.onSources(data.sources ?? []);
          break;
        case "token":
          cb.onToken(data.delta ?? "");
          break;
        case "done":
          cb.onDone({
            message_id: data.message_id ?? "",
            conversation_id: data.conversation_id,
            request_id: data.request_id ?? req.request_id,
            status: data.status ?? "complete",
          });
          break;
        case "error":
          cb.onError(data.message ?? data.detail ?? "回答生成失败", data.code);
          break;
      }
    },
    onerror(err) {
      throw err; // stop retrying
    },
  }).catch((err) => {
    if (!ctrl.signal.aborted) cb.onError(String(err));
  });

  return ctrl;
}
