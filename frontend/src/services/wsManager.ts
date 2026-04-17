import type { ErrorMessage, ErrorCategory, ProgressMessage } from "../types/ws";

interface ResultMessage {
  type: "result";
}

export interface WsCallbacks<TResult extends ResultMessage> {
  onProgress?: (message: ProgressMessage) => void;
  onResult?: (message: TResult) => void;
  onError?: (message: ErrorMessage) => void;
  onClose?: () => void;
}

export interface WsConnection {
  close: () => void;
}

const DEFAULT_ERROR_CODE = "WS_CLIENT_ERROR";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toStringValue(value: unknown, fallback: string): string {
  if (typeof value === "string") {
    return value;
  }

  return fallback;
}

function toNumberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  return null;
}

function toErrorCategory(value: unknown): ErrorCategory {
  const categories: ErrorCategory[] = [
    "request",
    "input",
    "dependency",
    "pipeline",
    "system",
    "not_implemented",
  ];

  if (typeof value === "string" && categories.includes(value as ErrorCategory)) {
    return value as ErrorCategory;
  }

  return "system";
}

function createClientError(message: string, detail?: string): ErrorMessage {
  return {
    type: "error",
    code: DEFAULT_ERROR_CODE,
    category: "system",
    message,
    stage: "websocket",
    retryable: true,
    detail,
  };
}

function normalizeBackendError(payload: Record<string, unknown>): ErrorMessage {
  return {
    type: "error",
    code: toStringValue(payload.code, DEFAULT_ERROR_CODE),
    category: toErrorCategory(payload.category),
    message: toStringValue(payload.message, "WebSocket 發生錯誤"),
    stage: toStringValue(payload.stage, "websocket"),
    retryable: Boolean(payload.retryable),
    detail: typeof payload.detail === "string" ? payload.detail : null,
  };
}

export function connectWs<TResult extends ResultMessage>(
  url: string,
  payload: unknown,
  callbacks: WsCallbacks<TResult>,
): WsConnection {
  let socket: WebSocket | null = null;
  let closedByClient = false;
  let resultReceived = false;
  let errorEmitted = false;

  const emitErrorOnce = (error: ErrorMessage): void => {
    if (errorEmitted) {
      return;
    }

    errorEmitted = true;
    callbacks.onError?.(error);
  };

  try {
    socket = new WebSocket(url);
  } catch (error) {
    emitErrorOnce(
      createClientError(
        "無法建立 WebSocket 連線",
        error instanceof Error ? error.message : undefined,
      ),
    );
    callbacks.onClose?.();
    return {
      close: () => {
        // Nothing to close when constructor failed.
      },
    };
  }

  socket.onopen = () => {
    try {
      socket?.send(JSON.stringify(payload));
    } catch (error) {
      emitErrorOnce(
        createClientError(
          "無法傳送 WebSocket 請求資料",
          error instanceof Error ? error.message : undefined,
        ),
      );
      socket?.close();
    }
  };

  socket.onmessage = (event) => {
    let rawPayload: unknown;

    try {
      rawPayload = JSON.parse(event.data as string);
    } catch {
      emitErrorOnce(createClientError("收到無法解析的 WebSocket 訊息"));
      return;
    }

    if (!isRecord(rawPayload)) {
      emitErrorOnce(createClientError("收到格式錯誤的 WebSocket 訊息"));
      return;
    }

    const messageType = toStringValue(rawPayload.type, "");

    if (messageType === "progress") {
      const percent = toNumberValue(rawPayload.percent);
      const message = toStringValue(rawPayload.message, "處理中");

      if (percent === null) {
        emitErrorOnce(createClientError("Progress 訊息缺少有效的 percent 欄位"));
        return;
      }

      callbacks.onProgress?.({
        type: "progress",
        percent,
        message,
      });
      return;
    }

    if (messageType === "error") {
      emitErrorOnce(normalizeBackendError(rawPayload));
      return;
    }

    if (messageType === "result") {
      resultReceived = true;
      callbacks.onResult?.(rawPayload as TResult);
      return;
    }

    emitErrorOnce(
      createClientError(`收到未知訊息類型: ${messageType || "<empty>"}`),
    );
  };

  socket.onerror = () => {
    emitErrorOnce(createClientError("WebSocket 連線錯誤"));
  };

  socket.onclose = () => {
    if (!closedByClient && !resultReceived && !errorEmitted) {
      emitErrorOnce(createClientError("WebSocket 連線意外中斷"));
    }

    callbacks.onClose?.();
  };

  return {
    close: () => {
      if (!socket) {
        return;
      }

      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        closedByClient = true;
        socket.close();
      }
    },
  };
}
