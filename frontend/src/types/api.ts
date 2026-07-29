export interface RetrievalConfig {
  top_k: number;
  private_weight: number;
  common_weight: number;
  min_chunks_common: number;
}

export interface IdentityOut {
  id: string;
  name: string;
  description: string;
  generation_model: string;
  retrieval: RetrievalConfig;
}

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  request_id?: string | null;
  status?: "pending" | "complete" | "stopped" | "failed";
  sources?: SourceItem[];
}

export interface ChatRequest {
  request_id: string;
  identity_id: string;
  message: string;
  conversation_id?: string | null;
}

export interface SourceItem {
  n: number;
  source_file: string;
  collection: string;
  score: number;
  document_id?: string | null;
  chunk_id?: string | null;
}

export interface IngestFileResult {
  file: string;
  chunks: number;
  error: string | null;
}

export interface IngestResult {
  identity_id: string;
  target: string;
  collection: string;
  files: IngestFileResult[];
  total_chunks: number;
}

export interface IngestSubmissionItem {
  file: string;
  document_id: string;
  job_id: string | null;
  status: string;
  duplicate: boolean;
  error: string | null;
}

export interface IngestSubmission {
  items: IngestSubmissionItem[];
}

export interface DocumentOut {
  id: string;
  identity_id: string | null;
  namespace: string;
  filename: string;
  content_type: string | null;
  sha256: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface IngestJobOut {
  id: string;
  document_id: string;
  status: string;
  error: string | null;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationOut {
  id: string;
  workspace_id: string;
  identity_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  role: string;
  content: string;
  sources_json: SourceItem[] | null;
  request_id: string | null;
  status: "pending" | "complete" | "stopped" | "failed";
  created_at: string;
}

export interface ChatProviderConfig {
  provider: string; // openai | anthropic
  base_url: string | null;
  api_key: string | null;
  model: string;
  clear_api_key: boolean;
}

export interface EmbeddingProviderConfig {
  provider: string; // huggingface | openai
  base_url: string | null;
  api_key: string | null;
  model: string;
  huggingface_endpoint: string | null;
  clear_api_key: boolean;
}

export interface ProvidersConfig {
  chat: ChatProviderConfig;
  embedding: EmbeddingProviderConfig;
}

export interface ProviderTestResult {
  chat: string;
  embedding: string;
}

export interface IndexVersionOut {
  id: string;
  namespace: "private" | "common";
  identity_id: string | null;
  logical_name: string;
  collection_name: string;
  embedding_provider: string;
  embedding_model: string;
  embedding_dim: number;
  status: string;
  created_at: string;
  updated_at: string;
}
