import { create } from "zustand";

import {
  getFileStatus,
  isFileServiceError,
} from "../services/fileService";
import { connectWs, type WsConnection } from "../services/wsManager";
import type {
  ErrorMessage,
  TranslateResultMessage,
  ProgressMessage,
} from "../types/ws";
import { useToastStore } from "./useToastStore";

type TranslateStatus =
  | "idle"
  | "checking"
  | "awaitingConfirm"
  | "translating"
  | "done"
  | "error";

interface TranslateRequestPayload {
  collection_name: string;
  method: "auto" | "txt" | "ocr";
  src_lang: "en";
  tgt_lang: "chinese_cht";
}

interface TranslateState {
  status: TranslateStatus;
  percent: number;
  message: string;
  result: TranslateResultMessage | null;
  errorMessage: string | null;
  connection: WsConnection | null;
  targetFilename: string | null;
  collectionName: string | null;
  pendingMethod: string | null;
  startTranslate: (collectionName: string) => Promise<void>;
  confirmOverwrite: () => void;
  cancelOverwrite: () => void;
  reset: () => void;
}

function clampPercent(value: number): number {
  if (value < 0) {
    return 0;
  }

  if (value > 100) {
    return 100;
  }

  return value;
}

function getTranslateWsUrl(): string {
  const baseWsUrl =
    (import.meta.env.VITE_BACKEND_WS_ORIGIN as string | undefined)
      ?.trim() || "ws://127.0.0.1:8080";

  return `${baseWsUrl.replace(/\/+$/, "")}/ws/translate`;
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

function failTranslate(
  set: (
    partial:
      | Partial<TranslateState>
      | ((state: TranslateState) => Partial<TranslateState>),
  ) => void,
  get: () => TranslateState,
  messageText: string,
  code: string | null = null,
  retryable: boolean = false,
): void {
  if (get().status === "error") {
    return;
  }

  const friendly = getFriendlyStageBusyMessage(code);
  const displayMessage = friendly ?? (retryable ? `${messageText}，請稍後再試` : messageText);

  set({
    status: "error",
    errorMessage: displayMessage,
    message: "",
    connection: null,
    pendingMethod: null,
  });

  useToastStore.getState().addToast("error", displayMessage);
}

function startWebSocketTranslate(
  collectionName: string,
  method: string,
  set: (partial: Partial<TranslateState> | ((state: TranslateState) => Partial<TranslateState>)) => void,
  get: () => TranslateState,
): void {
  let wsConnection: WsConnection | null = null;

  const payload: TranslateRequestPayload = {
    collection_name: collectionName,
    method: method as "auto" | "txt" | "ocr",
    src_lang: "en",
    tgt_lang: "chinese_cht",
  };

  wsConnection = connectWs<TranslateResultMessage>(getTranslateWsUrl(), payload, {
    onProgress: (progress: ProgressMessage) => {
      set({
        status: "translating",
        percent: clampPercent(progress.percent),
        message: progress.message,
        connection: wsConnection,
      });
    },
    onResult: (result: TranslateResultMessage) => {
      if (!result.success) {
        set({ result });
        failTranslate(
          set,
          get,
          result.error || "翻譯失敗",
          result.error_code || null,
          result.retryable ?? false,
        );
        wsConnection?.close();
        return;
      }

      set({
        status: "done",
        percent: 100,
        message: "翻譯完成",
        result,
        errorMessage: null,
        connection: null,
        pendingMethod: null,
      });

      useToastStore
        .getState()
        .addToast(
          "success",
          `翻譯完成，處理 ${result.translated_count} 段，耗時 ${result.processing_time.toFixed(2)} 秒`,
        );

      wsConnection?.close();
    },
    onError: (error: ErrorMessage) => {
      failTranslate(set, get, getErrorMessage(error), error.code || null, error.retryable);
    },
    onClose: () => {
      const current = get();

      if (current.status === "translating") {
        failTranslate(set, get, "與翻譯服務的連線已中斷", null);
        return;
      }

      set({ connection: null });
    },
  });

  set({
    status: "translating",
    percent: 0,
    message: "翻譯準備中...",
    errorMessage: null,
    connection: wsConnection,
    pendingMethod: null,
  });
}

export const useTranslateStore = create<TranslateState>((set, get) => ({
  status: "idle",
  percent: 0,
  message: "",
  result: null,
  errorMessage: null,
  connection: null,
  targetFilename: null,
  collectionName: null,
  pendingMethod: null,
  startTranslate: async (collectionName: string) => {
    const { status, connection } = get();

    if (
      status === "checking" ||
      status === "awaitingConfirm" ||
      status === "translating"
    ) {
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
        failTranslate(set, get, error.message, null);
      } else {
        const messageText =
          error instanceof Error ? error.message : "讀取檔案狀態失敗";
        failTranslate(set, get, messageText, null);
      }
      return;
    }

    if (get().status !== "checking") {
      return;
    }

    if (!statusResponse.is_parsed || !statusResponse.parse_method) {
      failTranslate(set, get, "檔案尚未解析，請先執行解析", null);
      return;
    }

    const method = statusResponse.parse_method;

    if (statusResponse.is_translated || statusResponse.is_indexed) {
      set({
        status: "awaitingConfirm",
        message: "檔案已有翻譯結果，等待覆寫確認",
        pendingMethod: method,
      });
      return;
    }

    startWebSocketTranslate(collectionName, method, set, get);
  },
  confirmOverwrite: () => {
    const current = get();

    if (current.status !== "awaitingConfirm" || !current.collectionName || !current.pendingMethod) {
      return;
    }

    const { collectionName, pendingMethod } = current;
    startWebSocketTranslate(collectionName, pendingMethod, set, get);
  },
  cancelOverwrite: () => {
    get().connection?.close();
    set({
      status: "idle",
      percent: 0,
      message: "",
      result: null,
      errorMessage: null,
      connection: null,
      pendingMethod: null,
      targetFilename: null,
      collectionName: null,
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
