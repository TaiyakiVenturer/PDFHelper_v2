import { create } from "zustand";

import {
  getFileStatus,
  isFileServiceError,
} from "../services/fileService";
import { connectWs, type WsConnection } from "../services/wsManager";
import type { ErrorMessage, IndexResultMessage, ProgressMessage } from "../types/ws";
import { useToastStore } from "./useToastStore";

type IndexStatus =
  | "idle"
  | "checking"
  | "awaitingConfirm"
  | "indexing"
  | "done"
  | "error";

interface IndexRequestPayload {
  collection_name: string;
  method: "auto" | "txt" | "ocr";
}

interface IndexState {
  status: IndexStatus;
  percent: number;
  message: string;
  result: IndexResultMessage | null;
  errorMessage: string | null;
  connection: WsConnection | null;
  targetFilename: string | null;
  collectionName: string | null;
  pendingMethod: string | null;
  startIndex: (collectionName: string) => Promise<void>;
  confirmOverwrite: () => void;
  cancelOverwrite: () => void;
  reset: () => void;
}

function clampPercent(value: number): number {
  if (value < 0) return 0;
  if (value > 100) return 100;
  return value;
}

function getIndexWsUrl(): string {
  const baseWsUrl =
    (import.meta.env.VITE_BACKEND_WS_ORIGIN as string | undefined)?.trim() ||
    "ws://127.0.0.1:12230";
  return `${baseWsUrl.replace(/\/+$/, "")}/ws/index`;
}

function getErrorMessage(error: ErrorMessage): string {
  if (error.detail) {
    return `${error.message} (${error.detail})`;
  }
  return error.message;
}

function getFriendlyStageBusyMessage(code?: string | null): string | null {
  if (code?.endsWith("_STAGE_BUSY")) {
    return "另一個任務正在執行中，請稍後再試";
  }
  return null;
}

function failIndex(
  set: (partial: Partial<IndexState> | ((state: IndexState) => Partial<IndexState>)) => void,
  get: () => IndexState,
  messageText: string,
  code: string | null = null,
  retryable: boolean = false,
): void {
  if (get().status === "error") return;

  const friendly = getFriendlyStageBusyMessage(code);

  if (friendly) {
    set({
      status: "idle",
      message: "",
      connection: null,
      errorMessage: null,
      pendingMethod: null,
    });
    useToastStore.getState().addToast("warning", friendly);
    return;
  }

  const displayMessage = retryable ? `${messageText}，請稍後再試` : messageText;

  set({
    status: "error",
    errorMessage: displayMessage,
    message: "",
    connection: null,
    pendingMethod: null,
  });

  useToastStore.getState().addToast("error", displayMessage);
}

export const useIndexStore = create<IndexState>((set, get) => ({
  status: "idle",
  percent: 0,
  message: "",
  result: null,
  errorMessage: null,
  connection: null,
  targetFilename: null,
  collectionName: null,
  pendingMethod: null,
  startIndex: async (collectionName: string) => {
    const { status, connection } = get();

    if (status === "checking" || status === "awaitingConfirm" || status === "indexing") {
      return;
    }

    connection?.close();

    set({
      status: "checking",
      percent: 0,
      message: "正在確認檔案狀態...",
      result: null,
      errorMessage: null,
      connection: null,
      targetFilename: collectionName,
      collectionName,
      pendingMethod: null,
    });

    let statusResponse;
    try {
      statusResponse = await getFileStatus(collectionName);
    } catch (error) {
      if (isFileServiceError(error)) {
        failIndex(set, get, error.message, null);
      } else {
        const messageText = error instanceof Error ? error.message : "讀取檔案狀態失敗";
        failIndex(set, get, messageText, null);
      }
      return;
    }

    if (get().status !== "checking") return;

    if (!statusResponse.is_parsed || !statusResponse.parse_method) {
      failIndex(set, get, "檔案尚未解析，請先執行解析", null);
      return;
    }

    const method = statusResponse.parse_method as IndexRequestPayload["method"];

    if (statusResponse.is_indexed) {
      set({
        status: "awaitingConfirm",
        message: "檔案已有索引結果，等待覆寫確認",
        pendingMethod: method,
      });
      return;
    }

    startWebSocketIndex(collectionName, method, set, get);
  },
  confirmOverwrite: () => {
    const current = get();

    if (!current.collectionName || !current.pendingMethod || current.status !== "awaitingConfirm") {
      return;
    }

    startWebSocketIndex(
      current.collectionName,
      current.pendingMethod as IndexRequestPayload["method"],
      set,
      get,
    );
  },
  cancelOverwrite: () => {
    if (get().status !== "awaitingConfirm") {
      return;
    }

    set({
      status: "idle",
      percent: 0,
      message: "",
      errorMessage: null,
      connection: null,
      pendingMethod: null,
    });
  },
  reset: () => {
    get().connection?.close();
    set({
      status: "idle",
      percent: 0,
      message: "",
      result: null,
      errorMessage: null,
      connection: null,
      targetFilename: null,
      collectionName: null,
      pendingMethod: null,
    });
  },
}));

function startWebSocketIndex(
  collectionName: string,
  method: IndexRequestPayload["method"],
  set: (partial: Partial<IndexState> | ((state: IndexState) => Partial<IndexState>)) => void,
  get: () => IndexState,
): void {
  let wsConnection: WsConnection | null = null;

  const payload: IndexRequestPayload = {
    collection_name: collectionName,
    method,
  };

  wsConnection = connectWs<IndexResultMessage>(getIndexWsUrl(), payload, {
    onProgress: (progress: ProgressMessage) => {
      set({
        status: "indexing",
        percent: clampPercent(progress.percent),
        message: progress.message,
        connection: wsConnection,
      });
    },
    onResult: (result: IndexResultMessage) => {
      if (!result.success) {
        set({ result });
        failIndex(set, get, result.error || "索引失敗", result.error_code || null, result.retryable ?? false);
        wsConnection?.close();
        return;
      }

      set({
        status: "done",
        percent: 100,
        message: "索引完成",
        result,
        errorMessage: null,
        connection: null,
        collectionName,
        pendingMethod: null,
      });

      useToastStore
        .getState()
        .addToast(
          "success",
          `索引完成，共切分 ${result.chunk_count} 個 chunk，耗時 ${result.processing_time.toFixed(2)} 秒`,
        );

      wsConnection?.close();
    },
    onError: (error: ErrorMessage) => {
      failIndex(set, get, getErrorMessage(error), error.code || null, error.retryable);
    },
    onClose: () => {
      const current = get();
      if (current.status === "indexing") {
        failIndex(set, get, "與索引服務的連線已中斷", null);
        return;
      }
      set({ connection: null });
    },
  });

  set({
    status: "indexing",
    percent: 0,
    message: "索引準備中...",
    errorMessage: null,
    connection: wsConnection,
    collectionName,
    pendingMethod: null,
  });
}
