import type {
  DocumentOut,
  IdentityOut,
  IngestJobOut,
  IngestResult,
  ProvidersConfig,
  ProviderTestResult,
} from "../types/api";

export async function getIdentities(): Promise<IdentityOut[]> {
  const r = await fetch("/api/identities");
  if (!r.ok) throw new Error(`Failed to load identities: ${r.status}`);
  return r.json();
}

export async function ingestDocuments(
  files: File[],
  identityId: string,
  target: "private" | "common"
): Promise<IngestResult> {
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

export async function getDocuments(): Promise<DocumentOut[]> {
  const r = await fetch("/api/documents");
  if (!r.ok) throw new Error(`Failed to load documents: ${r.status}`);
  return r.json();
}

export async function getIngestJobs(): Promise<IngestJobOut[]> {
  const r = await fetch("/api/ingest-jobs");
  if (!r.ok) throw new Error(`Failed to load ingest jobs: ${r.status}`);
  return r.json();
}
