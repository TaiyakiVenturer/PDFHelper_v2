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
  collection_name?: string | null;
  processing_time: number;
  error: string;
  error_code?: string | null;
  error_category?: ErrorCategory | null;
  retryable?: boolean;
}

export interface TranslateResultMessage {
  type: "result";
  success: boolean;
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
  chunk_count: number;
  processing_time: number;
  error: string;
  error_code?: string | null;
  error_category?: ErrorCategory | null;
  retryable?: boolean;
}

export type WsMessage = ProgressMessage | ErrorMessage | ParseResultMessage | TranslateResultMessage | IndexResultMessage;

export interface QuerySourceItem {
  page_idx: number;
  type_v2: string;
  text: string;
  section_title: string;
  chunk_id: string;
}

export interface QuerySourcesMessage {
  type: "sources";
  sources: QuerySourceItem[];
}

export interface QueryDeltaMessage {
  type: "delta";
  delta: string;
}

export interface QueryDoneMessage {
  type: "done";
  answer: string;
  processing_time: number;
}

export type QueryStreamMessage =
  | QuerySourcesMessage
  | QueryDeltaMessage
  | QueryDoneMessage
  | ErrorMessage;
