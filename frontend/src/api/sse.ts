import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { ChatRequest, SourceItem } from "../types/api";

export interface ChatStreamCallbacks {
  onSources: (sources: SourceItem[]) => void;
  onToken: (delta: string) => void;
  onDone: (messageId: string) => void;
  onError: (detail: string) => void;
}

/**
 * Stream a chat response from POST /api/chat using fetch-event-source
 * (native EventSource is GET-only and can't carry the JSON body).
 */
export function streamChat(req: ChatRequest, cb: ChatStreamCallbacks): AbortController {
  const ctrl = new AbortController();

  fetchEventSource("/api/chat", {
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
          cb.onDone(data.message_id ?? "");
          break;
        case "error":
          cb.onError(data.detail ?? "unknown error");
          break;
      }
    },
    onerror(err) {
      cb.onError(String(err));
      throw err; // stop retrying
    },
  });

  return ctrl;
}
