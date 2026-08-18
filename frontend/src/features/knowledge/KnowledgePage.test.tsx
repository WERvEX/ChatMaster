// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  deleteDocument: vi.fn(),
  getDocuments: vi.fn(),
  getIndexes: vi.fn(),
  getIngestJobs: vi.fn(),
  rebuildIndex: vi.fn(),
  retryIngestJob: vi.fn(),
}));

vi.mock("../../api/client", () => mocks);

import { KnowledgePage } from "./KnowledgePage";

describe("KnowledgePage", () => {
  it("uses an inline confirmation before deleting a document", async () => {
    mocks.getDocuments.mockResolvedValue([
      {
        id: "doc-1",
        identity_id: "persona-1",
        namespace: "private",
        filename: "产品资料.md",
        content_type: "text/markdown",
        sha256: "abc",
        status: "indexed",
        created_at: "2026-07-29T08:00:00Z",
        updated_at: "2026-07-29T08:00:00Z",
      },
    ]);
    mocks.getIndexes.mockResolvedValue([]);
    mocks.getIngestJobs.mockResolvedValue([]);
    mocks.deleteDocument.mockResolvedValue(undefined);

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={client}>
        <KnowledgePage identityId="persona-1" onBack={() => undefined} />
      </QueryClientProvider>
    );

    await screen.findByText("产品资料.md");
    expect(screen.getByLabelText("知识范围")).toBeInTheDocument();
    expect(screen.getByLabelText("处理状态")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "删除 产品资料.md" }));

    expect(screen.getByRole("alert")).toHaveTextContent("删除“产品资料.md”及其全部向量？");
    expect(mocks.deleteDocument).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(mocks.deleteDocument).toHaveBeenCalledWith("doc-1"));
  });

  it("rebuilds a private index for the identity recorded on that index", async () => {
    mocks.getDocuments.mockResolvedValue([]);
    mocks.getIngestJobs.mockResolvedValue([]);
    mocks.getIndexes.mockResolvedValue([
      {
        id: "index-private-2",
        namespace: "private",
        identity_id: "persona-2",
        collection_name: "persona-2-v1",
        logical_name: "persona-2",
        embedding_provider: "huggingface",
        embedding_model: "BAAI/bge-small-zh-v1.5",
        embedding_dim: 384,
        config_fingerprint: "test",
        status: "stale",
        created_at: "2026-07-29T08:00:00Z",
        updated_at: "2026-07-29T08:00:00Z",
      },
    ]);
    mocks.rebuildIndex.mockResolvedValue(undefined);

    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <KnowledgePage identityId="persona-1" onBack={() => undefined} />
      </QueryClientProvider>
    );

    const rebuildButton = await screen.findByRole("button", { name: "重建" });
    fireEvent.click(rebuildButton);

    await waitFor(() =>
      expect(mocks.rebuildIndex).toHaveBeenCalledWith("private", "persona-2")
    );
  });
});
