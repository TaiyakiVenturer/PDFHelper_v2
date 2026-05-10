export type LLMBackend = "llama_cpp" | "openai_compat";

export interface LlamaCppConfig {
  repo_id: string;
  filename: string;
  n_gpu_layers: number;
  n_ctx: number;
}

export interface OpenAICompatConfig {
  base_url: string;
  api_key: string;
  model: string;
}

export interface LLMConfig {
  backend: LLMBackend;
  temperature: number;
  max_tokens: number;
  query_history_turns: number;
  llama_cpp: LlamaCppConfig;
  openai_compat: OpenAICompatConfig;
}

export interface AppConfig {
  llm: LLMConfig;
}

export interface LocalModelsResponse {
  files: string[];
}

export interface ProbeRequest {
  base_url: string;
  api_key: string;
}

export interface ProbeResponse {
  ok: boolean;
  models: string[];
  error?: string;
}
