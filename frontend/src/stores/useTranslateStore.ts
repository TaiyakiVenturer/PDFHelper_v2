import { create } from "zustand";

import {
  deriveCollectionName,
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
  json_path: string;
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
  pendingJsonPath: string | null;
  startTranslate: (filename: string, filePath: string) => Promise<void>;
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
  if (code === "STAGE_BUSY") {
    return "另一個任務正在執行中，請稍後再試";
  }

  return null;
}

function getFilenameFromPath(path: string): string {
  const normalized = path.trim();
  if (!normalized) {
    return "";
  }

  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || "";
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
): void {
  if (get().status === "error") {
    return;
  }

  set({
    status: "error",
    errorMessage: messageText,
    message: "",
    connection: null,
    pendingJsonPath: null,
  });

  const friendly = getFriendlyStageBusyMessage(code);
  useToastStore.getState().addToast("error", friendly || messageText);
}

export const useTranslateStore = create<TranslateState>((set, get) => ({
  status: "idle",
  percent: 0,
  message: "",
  result: null,
  errorMessage: null,
  connection: null,
  targetFilename: null,
  pendingJsonPath: null,
  startTranslate: async (filename: string, filePath: string) => {
    const { status, connection } = get();

    if (
      status === "checking" ||
      status === "awaitingConfirm" ||
      status === "translating"
    ) {
      return;
    }

    connection?.close();

    const fallbackName = getFilenameFromPath(filePath);
    const targetName = filename.trim() || fallbackName;
    const collectionName = deriveCollectionName(targetName);

    if (!collectionName) {
      failTranslate(set, get, "無法判斷檔案名稱，請重新選擇檔案");
      return;
    }

    set({
      status: "checking",
      percent: 0,
      message: "正在確認檔案狀態...",
      result: null,
      errorMessage: null,
      connection: null,
      targetFilename: targetName,
      pendingJsonPath: null,
    });

    let statusResponse;
    try {
      statusResponse = await getFileStatus(collectionName, "auto");
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

    if (statusResponse.stage === "none") {
      failTranslate(set, get, "檔案尚未解析，請先執行解析", null);
      return;
    }

    const parseJsonPath = statusResponse.json_path;

    if (!parseJsonPath) {
      failTranslate(set, get, "找不到解析結果，請先解析該檔案", null);
      return;
    }

    if (
      statusResponse.stage === "translated" ||
      statusResponse.stage === "indexed"
    ) {
      set({
        status: "awaitingConfirm",
        message: "檔案已有翻譯結果，等待覆寫確認",
        pendingJsonPath: parseJsonPath,
      });
      return;
    }

    const startWebSocketTranslate = (jsonPath: string): void => {
      let wsConnection: WsConnection | null = null;

      const payload: TranslateRequestPayload = {
        json_path: jsonPath,
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
            pendingJsonPath: null,
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
          failTranslate(set, get, getErrorMessage(error), error.code || null);
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
        pendingJsonPath: null,
      });
    };

    startWebSocketTranslate(parseJsonPath);
  },
  confirmOverwrite: () => {
    const current = get();

    if (current.status !== "awaitingConfirm" || !current.pendingJsonPath) {
      return;
    }

    const jsonPath = current.pendingJsonPath;
    set({
      status: "translating",
      percent: 0,
      message: "翻譯準備中...",
      errorMessage: null,
      pendingJsonPath: null,
    });

    let wsConnection: WsConnection | null = null;

    const payload: TranslateRequestPayload = {
      json_path: jsonPath,
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
          pendingJsonPath: null,
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
        failTranslate(set, get, getErrorMessage(error), error.code || null);
      },
      onClose: () => {
        const currentState = get();

        if (currentState.status === "translating") {
          failTranslate(set, get, "與翻譯服務的連線已中斷", null);
          return;
        }

        set({ connection: null });
      },
    });

    set({ connection: wsConnection });
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
      pendingJsonPath: null,
      targetFilename: null,
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
      pendingJsonPath: null,
    });
  },
}));
