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
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  identity_id: string;
  message: string;
  history: Message[];
  conversation_id?: string | null;
}

export interface SourceItem {
  n: number;
  source_file: string;
  collection: string;
  score: number;
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

export interface ChatProviderConfig {
  provider: string; // openai | anthropic
  base_url: string | null;
  api_key: string | null;
  model: string;
}

export interface EmbeddingProviderConfig {
  provider: string; // huggingface | openai
  base_url: string | null;
  api_key: string | null;
  model: string;
  huggingface_endpoint: string | null;
}

export interface ProvidersConfig {
  chat: ChatProviderConfig;
  embedding: EmbeddingProviderConfig;
}

export interface ProviderTestResult {
  chat: string;
  embedding: string;
}
