import { create } from "zustand";

import {
  deriveCollectionName,
  getFileStatus,
  isFileServiceError,
} from "../services/fileService";
import { connectWs, type WsConnection } from "../services/wsManager";
import type { ErrorMessage, IndexResultMessage, ProgressMessage } from "../types/ws";
import { useToastStore } from "./useToastStore";

type IndexStatus = "idle" | "checking" | "indexing" | "done" | "error";

interface IndexRequestPayload {
  json_path: string;
}

interface IndexState {
  status: IndexStatus;
  percent: number;
  message: string;
  result: IndexResultMessage | null;
  errorMessage: string | null;
  connection: WsConnection | null;
  targetFilename: string | null;
  startIndex: (filename: string, filePath: string) => Promise<void>;
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
    "ws://127.0.0.1:8080";
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

function getFilenameFromPath(path: string): string {
  const normalized = path.trim();
  if (!normalized) return "";
  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || "";
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
    set({ status: "idle", message: "", connection: null, errorMessage: null });
    useToastStore.getState().addToast("warning", friendly);
    return;
  }

  const displayMessage = retryable ? `${messageText}，請稍後再試` : messageText;

  set({
    status: "error",
    errorMessage: displayMessage,
    message: "",
    connection: null,
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
  startIndex: async (filename: string, filePath: string) => {
    const { status, connection } = get();

    if (status === "checking" || status === "indexing") {
      return;
    }

    connection?.close();

    const fallbackName = getFilenameFromPath(filePath);
    const targetName = filename.trim() || fallbackName;
    const collectionName = deriveCollectionName(targetName);

    if (!collectionName) {
      failIndex(set, get, "無法判斷檔案名稱，請重新選擇檔案");
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
    });

    let statusResponse;
    try {
      statusResponse = await getFileStatus(collectionName, "auto");
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

    if (statusResponse.stage === "none") {
      failIndex(set, get, "檔案尚未解析，請先執行解析", null);
      return;
    }

    const parseJsonPath = statusResponse.json_path;

    if (!parseJsonPath) {
      failIndex(set, get, "找不到解析結果，請先解析該檔案", null);
      return;
    }

    let wsConnection: WsConnection | null = null;

    const payload: IndexRequestPayload = { json_path: parseJsonPath };

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
    });
  },
}));
