import type {
  ConversationOut,
  DocumentOut,
  IdentityDetail,
  IdentityOut,
  IdentityPayload,
  IngestJobOut,
  IngestSubmission,
  IndexVersionOut,
  MessageOut,
  ProvidersConfig,
  ProviderTestResult,
} from "../types/api";

export async function getIdentities(includeArchived = false): Promise<IdentityOut[]> {
  const r = await fetch(`/api/identities${includeArchived ? "?include_archived=true" : ""}`);
  if (!r.ok) throw new Error(`Failed to load identities: ${r.status}`);
  return r.json();
}

export async function getIdentity(identityId: string): Promise<IdentityDetail> {
  const r = await fetch(`/api/identities/${encodeURIComponent(identityId)}`);
  if (!r.ok) throw new Error(`Failed to load identity: ${r.status}`);
  return r.json();
}

export async function createIdentity(payload: IdentityPayload): Promise<IdentityDetail> {
  const r = await fetch("/api/identities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`Create identity failed: ${r.status}`);
  return r.json();
}

export async function updateIdentity(
  identityId: string,
  payload: IdentityPayload
): Promise<IdentityDetail> {
  const r = await fetch(`/api/identities/${encodeURIComponent(identityId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`Update identity failed: ${r.status}`);
  return r.json();
}

async function postIdentityAction(identityId: string, action: string): Promise<IdentityDetail> {
  const r = await fetch(
    `/api/identities/${encodeURIComponent(identityId)}/${action}`,
    { method: "POST" }
  );
  if (!r.ok) throw new Error(`${action} identity failed: ${r.status}`);
  return r.json();
}

export const archiveIdentity = (identityId: string) =>
  postIdentityAction(identityId, "archive");
export const restoreIdentity = (identityId: string) =>
  postIdentityAction(identityId, "restore");
export const duplicateIdentity = (identityId: string) =>
  postIdentityAction(identityId, "duplicate");

export async function ingestDocuments(
  files: File[],
  identityId: string,
  target: "private" | "common"
): Promise<IngestSubmission> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("identity_id", identityId);
  form.append("target", target);
  const r = await fetch("/api/documents/ingest", { method: "POST", body: form });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`Ingest failed (${r.status}): ${detail}`);
  }
  return r.json();
}

export async function retryIngestJob(jobId: string): Promise<IngestJobOut> {
  const r = await fetch(`/api/ingest-jobs/${jobId}/retry`, { method: "POST" });
  if (!r.ok) throw new Error(`Retry failed: ${r.status}`);
  return r.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  const r = await fetch(`/api/documents/${documentId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
}

export async function getIndexes(): Promise<IndexVersionOut[]> {
  const r = await fetch("/api/indexes");
  if (!r.ok) throw new Error(`Failed to load indexes: ${r.status}`);
  return r.json();
}

export async function rebuildIndex(
  target: "private" | "common",
  identityId?: string | null
): Promise<void> {
  const r = await fetch("/api/indexes/rebuild", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, identity_id: identityId ?? null }),
  });
  if (!r.ok) throw new Error(`Rebuild failed: ${r.status}`);
}

export async function cancelChat(requestId: string): Promise<boolean> {
  const r = await fetch(`/api/chat/${encodeURIComponent(requestId)}/cancel`, {
    method: "POST",
  });
  if (!r.ok) return false;
  const body = await r.json();
  return Boolean(body.cancelled);
}

export async function getProviders(): Promise<ProvidersConfig> {
  const r = await fetch("/api/providers");
  if (!r.ok) throw new Error(`Failed to load providers: ${r.status}`);
  return r.json();
}

export async function saveProviders(cfg: ProvidersConfig): Promise<ProvidersConfig> {
  const r = await fetch("/api/providers", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`Save failed (${r.status}): ${detail}`);
  }
  return r.json();
}

export async function testProviders(): Promise<ProviderTestResult> {
  const r = await fetch("/api/providers/test", { method: "POST" });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`Test failed (${r.status}): ${detail}`);
  }
  return r.json();
}

export async function getDocuments(filters?: {
  identityId?: string | null;
  namespace?: "private" | "common" | "";
  status?: string;
}): Promise<DocumentOut[]> {
  const params = new URLSearchParams();
  if (filters?.identityId) params.set("identity_id", filters.identityId);
  if (filters?.namespace) params.set("namespace", filters.namespace);
  if (filters?.status) params.set("status", filters.status);
  const r = await fetch(`/api/documents?${params}`);
  if (!r.ok) throw new Error(`Failed to load documents: ${r.status}`);
  return r.json();
}

export async function getIngestJobs(status?: string): Promise<IngestJobOut[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const r = await fetch(`/api/ingest-jobs?${params}`);
  if (!r.ok) throw new Error(`Failed to load ingest jobs: ${r.status}`);
  return r.json();
}

export async function getConversations(identityId: string): Promise<ConversationOut[]> {
  const r = await fetch(`/api/conversations?identity_id=${encodeURIComponent(identityId)}`);
  if (!r.ok) throw new Error(`Failed to load conversations: ${r.status}`);
  return r.json();
}

export async function createConversation(
  identityId: string,
  title?: string
): Promise<ConversationOut> {
  const r = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identity_id: identityId, title }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`Create conversation failed (${r.status}): ${detail}`);
  }
  return r.json();
}

export async function getConversationMessages(conversationId: string): Promise<MessageOut[]> {
  const r = await fetch(`/api/conversations/${conversationId}/messages`);
  if (!r.ok) throw new Error(`Failed to load messages: ${r.status}`);
  return r.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const r = await fetch(`/api/conversations/${conversationId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`Delete conversation failed: ${r.status}`);
}

export async function updateConversation(
  conversationId: string,
  title: string
): Promise<ConversationOut> {
  const r = await fetch(`/api/conversations/${conversationId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!r.ok) throw new Error(`Rename conversation failed: ${r.status}`);
  return r.json();
}
