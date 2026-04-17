import { create } from "zustand";

import { connectWs, type WsConnection } from "../services/wsManager";
import type { ErrorMessage, ParseResultMessage, ProgressMessage } from "../types/ws";
import { useToastStore } from "./useToastStore";

type ParseStatus = "idle" | "parsing" | "done" | "error";

interface ParseRequestPayload {
  pdf_path: string;
  method: "auto" | "txt" | "ocr";
  lang: string;
  formula: boolean;
  table: boolean;
}

interface ParseState {
  status: ParseStatus;
  percent: number;
  message: string;
  result: ParseResultMessage | null;
  errorMessage: string | null;
  connection: WsConnection | null;
  startParse: (pdfPath: string) => Promise<void>;
  updateProgress: (percent: number, message: string) => void;
  setResult: (result: ParseResultMessage) => void;
  setError: (errorMessage: string) => void;
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

function getParseWsUrl(): string {
  const baseWsUrl = (import.meta.env.VITE_BACKEND_WS_ORIGIN as string | undefined)?.trim() ||
    "ws://127.0.0.1:8080";

  return `${baseWsUrl.replace(/\/+$/, "")}/ws/parse`;
}

function getErrorMessage(error: ErrorMessage): string {
  if (error.detail) {
    return `${error.message} (${error.detail})`;
  }

  return error.message;
}

export const useParseStore = create<ParseState>((set, get) => ({
  status: "idle",
  percent: 0,
  message: "",
  result: null,
  errorMessage: null,
  connection: null,
  startParse: async (pdfPath: string) => {
    const { status, connection } = get();

    if (status === "parsing") {
      return;
    }

    connection?.close();

    set({
      status: "parsing",
      percent: 0,
      message: "準備解析中...",
      result: null,
      errorMessage: null,
      connection: null,
    });

    const payload: ParseRequestPayload = {
      pdf_path: pdfPath,
      method: "auto",
      lang: "en",
      formula: true,
      table: true,
    };

    let wsConnection: WsConnection | null = null;

    const failParse = (messageText: string): void => {
      if (get().status === "error") {
        return;
      }

      set({
        status: "error",
        errorMessage: messageText,
        message: "",
        connection: null,
      });

      useToastStore.getState().addToast("error", messageText);
      wsConnection?.close();
    };

    wsConnection = connectWs<ParseResultMessage>(getParseWsUrl(), payload, {
      onProgress: (progress: ProgressMessage) => {
        set({
          status: "parsing",
          percent: clampPercent(progress.percent),
          message: progress.message,
        });
      },
      onResult: (result: ParseResultMessage) => {
        if (!result.success) {
          set({ result });
          failParse(result.error || "解析失敗");
          return;
        }

        set({
          status: "done",
          percent: 100,
          message: "解析完成",
          result,
          errorMessage: null,
          connection: null,
        });

        useToastStore
          .getState()
          .addToast("success", `解析完成，耗時 ${result.processing_time.toFixed(2)} 秒`);

        wsConnection?.close();
      },
      onError: (error: ErrorMessage) => {
        failParse(getErrorMessage(error));
      },
      onClose: () => {
        const current = get();

        if (current.status === "parsing") {
          failParse("與解析服務的連線已中斷");
          return;
        }

        set({ connection: null });
      },
    });

    set({ connection: wsConnection });
  },
  updateProgress: (percent: number, message: string) => {
    set({
      status: "parsing",
      percent: clampPercent(percent),
      message,
    });
  },
  setResult: (result: ParseResultMessage) => {
    set({
      status: result.success ? "done" : "error",
      result,
      percent: result.success ? 100 : 0,
      message: result.success ? "解析完成" : "",
      errorMessage: result.success ? null : result.error || "解析失敗",
      connection: null,
    });
  },
  setError: (errorMessage: string) => {
    set({
      status: "error",
      errorMessage,
      message: "",
      connection: null,
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
    });
  },
}));
