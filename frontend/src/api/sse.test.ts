import { describe, expect, it, vi } from "vitest";

const { fetchEventSource } = vi.hoisted(() => ({ fetchEventSource: vi.fn() }));
vi.mock("@microsoft/fetch-event-source", () => ({ fetchEventSource }));

import { streamChat } from "./sse";

const request = {
  request_id: "00000000-0000-4000-8000-000000000001",
  identity_id: "legal_expert",
  message: "hello",
};

describe("streamChat", () => {
  it("reports a rejected stream once", async () => {
    fetchEventSource.mockRejectedValueOnce(new Error("offline"));
    const onError = vi.fn();
    streamChat(request, { onSources: vi.fn(), onToken: vi.fn(), onDone: vi.fn(), onError });
    await Promise.resolve();
    await Promise.resolve();
    expect(onError).toHaveBeenCalledWith("Error: offline");
  });

  it("does not report an aborted stream as an error", async () => {
    fetchEventSource.mockRejectedValueOnce(new Error("aborted"));
    const onError = vi.fn();
    const controller = streamChat(request, {
      onSources: vi.fn(), onToken: vi.fn(), onDone: vi.fn(), onError,
    });
    controller.abort();
    await Promise.resolve();
    await Promise.resolve();
    expect(onError).not.toHaveBeenCalled();
  });
});
