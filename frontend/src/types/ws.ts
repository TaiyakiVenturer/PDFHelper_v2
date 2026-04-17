export type ErrorCategory =
  | "request"
  | "input"
  | "dependency"
  | "pipeline"
  | "system"
  | "not_implemented";

export interface ProgressMessage {
  type: "progress";
  percent: number;
  message: string;
}

export interface ErrorMessage {
  type: "error";
  code: string;
  category: ErrorCategory;
  message: string;
  stage: string;
  retryable: boolean;
  detail?: string | null;
}

export interface ParseResultMessage {
  type: "result";
  success: boolean;
  markdown_path?: string | null;
  json_path?: string | null;
  image_dir?: string | null;
  processing_time: number;
  error: string;
  error_code?: string | null;
  error_category?: ErrorCategory | null;
  retryable?: boolean;
}

export interface TranslateResultMessage {
  type: "result";
  success: boolean;
  translated_path?: string | null;
  translated_count: number;
  skipped_count: number;
  processing_time: number;
  error: string;
  error_code?: string | null;
  error_category?: ErrorCategory | null;
  retryable?: boolean;
}

export interface IndexResultMessage {
  type: "result";
  success: boolean;
  collection_name?: string | null;
  chunk_count: number;
  processing_time: number;
  error: string;
  error_code?: string | null;
  error_category?: ErrorCategory | null;
  retryable?: boolean;
}

export type WsMessage = ProgressMessage | ErrorMessage | ParseResultMessage;
