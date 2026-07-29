// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  cancelChat: vi.fn(),
  getConversationMessages: vi.fn(),
  streamChat: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  cancelChat: mocks.cancelChat,
  getConversationMessages: mocks.getConversationMessages,
}));
vi.mock("../../api/sse", () => ({ streamChat: mocks.streamChat }));

import { useChat } from "./useChat";

describe("useChat", () => {
  it("does not reload and overwrite optimistic messages for a new conversation", async () => {
    mocks.cancelChat.mockResolvedValue(false);
    mocks.getConversationMessages.mockResolvedValueOnce([]);
    mocks.streamChat.mockImplementationOnce((_request, callbacks) => {
      queueMicrotask(() =>
        callbacks.onDone({
          message_id: "message-1",
          conversation_id: "conversation-1",
          request_id: "request-1",
          status: "complete",
        })
      );
      return new AbortController();
    });
    const onConversationId = vi.fn();

    const { result, rerender } = renderHook(
      ({ conversationId }) => useChat("legal_expert", { conversationId, onConversationId }),
      { initialProps: { conversationId: null as string | null } }
    );

    await act(async () => {
      await result.current.sendMessage("你好");
      await Promise.resolve();
    });
    rerender({ conversationId: "conversation-1" });

    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(mocks.getConversationMessages).not.toHaveBeenCalled();
    expect(result.current.messages[0]).toMatchObject({ role: "user", content: "你好" });
    expect(onConversationId).toHaveBeenCalledWith("conversation-1");
  });
});
