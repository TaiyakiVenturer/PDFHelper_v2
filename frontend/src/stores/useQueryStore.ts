import { create } from "zustand";

import { getFileStatus, isFileServiceError } from "../services/fileService";
import { connectStreamWs, type WsConnection } from "../services/wsManager";
import type {
  ErrorMessage,
  QueryDeltaMessage,
  QueryDoneMessage,
  QuerySourceItem,
  QuerySourcesMessage,
} from "../types/ws";
import { useToastStore } from "./useToastStore";

type QueryStatus =
  | "idle"
  | "checking"
  | "retrieving"
  | "generating"
  | "done"
  | "error";

type InterruptedAt = "before_sources" | "after_sources" | "during_delta" | null;

interface QueryRequestPayload {
  question: string;
  collection_name: string;
  top_k: number;
  history: unknown[];
}

interface QueryResult {
  answer: string;
  processing_time: number;
}

interface QueryState {
  status: QueryStatus;
  question: string;
  sources: QuerySourceItem[];
  answer: string;
  interruptedAt: InterruptedAt;
  errorMessage: string | null;
  result: QueryResult | null;
  connection: WsConnection | null;
  scrollTarget: { sectionTitle: string; pageIdx: number; chunkText: string } | null;
  submitQuery: (question: string, collectionName: string) => Promise<void>;
  setScrollTarget: (sectionTitle: string, pageIdx: number, chunkText: string) => void;
  reset: () => void;
}

function getQueryWsUrl(): string {
  const baseWsUrl =
    (import.meta.env.VITE_BACKEND_WS_ORIGIN as string | undefined)?.trim() ||
    "ws://127.0.0.1:8080";
  return `${baseWsUrl.replace(/\/+$/, "")}/ws/query`;
}

function getErrorMessage(error: ErrorMessage): string {
  if (error.detail) {
    return `${error.message} (${error.detail})`;
  }
  return error.message;
}

function resolveInterruptedAt(currentStatus: QueryStatus): InterruptedAt {
  if (currentStatus === "checking" || currentStatus === "retrieving") {
    return "before_sources";
  }
  if (currentStatus === "generating") {
    return "during_delta";
  }
  return "after_sources";
}

function failQuery(
  set: (partial: Partial<QueryState> | ((state: QueryState) => Partial<QueryState>)) => void,
  get: () => QueryState,
  messageText: string,
  code: string | null = null,
  retryable: boolean = false,
): void {
  const currentStatus = get().status;
  if (currentStatus === "error") return;

  if (code?.endsWith("_STAGE_BUSY")) {
    set({ status: "idle", question: "", sources: [], answer: "", interruptedAt: null, errorMessage: null, connection: null });
    useToastStore.getState().addToast("warning", "另一個任務正在執行中，請稍後再試");
    return;
  }

  const displayMessage = retryable ? `${messageText}，請稍後再試` : messageText;

  set({
    status: "error",
    errorMessage: displayMessage,
    interruptedAt: resolveInterruptedAt(currentStatus),
    connection: null,
  });
}

export const useQueryStore = create<QueryState>((set, get) => ({
  status: "idle",
  question: "",
  sources: [],
  answer: "",
  interruptedAt: null,
  errorMessage: null,
  result: null,
  connection: null,
  scrollTarget: null,
  submitQuery: async (question: string, collectionName: string) => {
    if (!question.trim()) {
      useToastStore.getState().addToast("warning", "請輸入問題後再送出");
      return;
    }

    const { status, connection } = get();
    if (status === "checking" || status === "retrieving" || status === "generating") {
      return;
    }

    connection?.close();

    set({
      status: "checking",
      question,
      sources: [],
      answer: "",
      interruptedAt: null,
      errorMessage: null,
      result: null,
      connection: null,
    });

    let statusResponse;
    try {
      statusResponse = await getFileStatus(collectionName);
    } catch (error) {
      if (isFileServiceError(error)) {
        failQuery(set, get, error.message);
      } else {
        const messageText = error instanceof Error ? error.message : "讀取檔案狀態失敗";
        failQuery(set, get, messageText);
      }
      return;
    }

    if (get().status !== "checking") return;

    if (!statusResponse.is_indexed) {
      failQuery(set, get, "請先為該檔案建立索引");
      return;
    }

    set({ status: "retrieving" });

    let wsConnection: WsConnection | null = null;

    const payload: QueryRequestPayload = {
      question,
      collection_name: collectionName,
      top_k: 5,
      history: [],
    };

    wsConnection = connectStreamWs<QuerySourcesMessage, QueryDeltaMessage, QueryDoneMessage>(
      getQueryWsUrl(),
      payload,
      {
        onSources: (message: QuerySourcesMessage) => {
          set({
            sources: message.sources,
            status: "generating",
          });
        },
        onDelta: (message: QueryDeltaMessage) => {
          set((state) => ({ answer: state.answer + message.delta }));
        },
        onDone: (message: QueryDoneMessage) => {
          set({
            status: "done",
            result: {
              answer: message.answer,
              processing_time: message.processing_time,
            },
            connection: null,
          });
          wsConnection?.close();
        },
        onError: (error: ErrorMessage) => {
          failQuery(set, get, getErrorMessage(error), error.code ?? null, error.retryable);
        },
        onClose: () => {
          const current = get();
          if (
            current.status === "retrieving" ||
            current.status === "generating" ||
            current.status === "checking"
          ) {
            failQuery(set, get, "與查詢服務的連線已中斷");
            return;
          }
          set({ connection: null });
        },
      },
    );

    set({ connection: wsConnection });
  },
  setScrollTarget: (sectionTitle, pageIdx, chunkText) => set({ scrollTarget: { sectionTitle, pageIdx, chunkText } }),
  reset: () => {
    get().connection?.close();
    set({
      status: "idle",
      question: "",
      sources: [],
      answer: "",
      interruptedAt: null,
      errorMessage: null,
      result: null,
      connection: null,
      scrollTarget: null,
    });
  },
}));
