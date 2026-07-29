// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversations: vi.fn(),
}));

vi.mock("../api/client", () => ({
  createConversation: mocks.createConversation,
  deleteConversation: mocks.deleteConversation,
  getConversations: mocks.getConversations,
}));

import { useConversations } from "./useConversations";

describe("useConversations", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("deletes the active conversation without creating a replacement", async () => {
    mocks.getConversations.mockResolvedValueOnce([
      {
        id: "conversation-1",
        workspace_id: "local",
        identity_id: "legal_expert",
        title: "测试会话",
        created_at: "2026-07-28T00:00:00Z",
        updated_at: "2026-07-28T00:00:00Z",
      },
    ]);
    mocks.deleteConversation.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useConversations("legal_expert"));
    await waitFor(() => expect(result.current.activeId).toBe("conversation-1"));

    await act(async () => {
      await result.current.deleteActiveConversation();
    });

    expect(mocks.deleteConversation).toHaveBeenCalledWith("conversation-1");
    expect(mocks.createConversation).not.toHaveBeenCalled();
    expect(result.current.activeId).toBeNull();
    expect(result.current.conversations).toEqual([]);
  });
});
