export interface PdfFileItem {
  name: string;
  path: string;
}

export type FileStage = "none" | "parsed" | "translated" | "indexed";

export interface FileStatusResponse {
  stage: FileStage;
  translated_path: string | null;
  collection_name: string | null;
}

interface FileListResponse {
  files: PdfFileItem[];
}

const BACKEND_HTTP_ORIGIN = (import.meta.env.VITE_BACKEND_HTTP_ORIGIN as string | undefined)?.trim() ||
  "http://127.0.0.1:8080";
const API_BASE = BACKEND_HTTP_ORIGIN.replace(/\/+$/, "");

export type FileServiceErrorCode = "NETWORK" | "CONFLICT" | "BAD_REQUEST" | "NOT_FOUND" | "SERVER";

export class FileServiceError extends Error {
  code: FileServiceErrorCode;
  status: number | null;

  constructor(code: FileServiceErrorCode, message: string, status: number | null = null) {
    super(message);
    this.name = "FileServiceError";
    this.code = code;
    this.status = status;
  }
}

export function isFileServiceError(error: unknown): error is FileServiceError {
  return error instanceof FileServiceError;
}

export function deriveCollectionName(filename: string): string {
  const trimmed = filename.trim();
  if (!trimmed) {
    return "";
  }

  const dotIndex = trimmed.lastIndexOf(".");
  if (dotIndex <= 0) {
    return trimmed;
  }

  return trimmed.slice(0, dotIndex);
}

async function readErrorDetail(response: Response): Promise<string | null> {
  const raw = await response.text();
  if (!raw.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }

    if (typeof parsed.message === "string" && parsed.message.trim()) {
      return parsed.message;
    }
  } catch {
    // Fallback to plain text body.
  }

  return raw;
}

function toNetworkError(error: unknown): FileServiceError {
  if (error instanceof FileServiceError) {
    return error;
  }

  const detail = error instanceof Error ? error.message : "";
  const suffix = detail ? ` (${detail})` : "";
  return new FileServiceError("NETWORK", `無法連線後端服務，請確認後端是否啟動${suffix}`);
}

export async function listPdfs(): Promise<PdfFileItem[]> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/files`, { method: "GET" });
  } catch (error) {
    throw toNetworkError(error);
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new FileServiceError(
      "SERVER",
      detail ? `讀取 PDF 列表失敗：${detail}` : `讀取 PDF 列表失敗（HTTP ${response.status}）`,
      response.status,
    );
  }

  const payload = (await response.json()) as FileListResponse;
  return Array.isArray(payload.files) ? payload.files : [];
}

export async function copyPdfToDataDir(sourcePath: string): Promise<PdfFileItem> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/file/upload`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ source_path: sourcePath }),
    });
  } catch (error) {
    throw toNetworkError(error);
  }

  if (response.ok) {
    return (await response.json()) as PdfFileItem;
  }

  const detail = await readErrorDetail(response);

  if (response.status === 409) {
    throw new FileServiceError(
      "CONFLICT",
      detail || "檔案已存在，請先刪除舊檔再上傳",
      response.status,
    );
  }

  if (response.status === 400) {
    throw new FileServiceError(
      "BAD_REQUEST",
      detail || "不支援的檔案格式或路徑無效",
      response.status,
    );
  }

  if (response.status === 404) {
    throw new FileServiceError(
      "NOT_FOUND",
      detail || "找不到來源檔案",
      response.status,
    );
  }

  throw new FileServiceError(
    "SERVER",
    detail || `上傳失敗（HTTP ${response.status}）`,
    response.status,
  );
}

export async function deletePdf(filename: string): Promise<void> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/file/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
  } catch (error) {
    throw toNetworkError(error);
  }

  if (response.ok) {
    return;
  }

  const detail = await readErrorDetail(response);

  if (response.status === 404) {
    throw new FileServiceError(
      "NOT_FOUND",
      detail || "檔案不存在或已刪除",
      response.status,
    );
  }

  if (response.status === 400) {
    throw new FileServiceError(
      "BAD_REQUEST",
      detail || "檔名格式不合法",
      response.status,
    );
  }

  throw new FileServiceError(
    "SERVER",
    detail || `刪除失敗（HTTP ${response.status}）`,
    response.status,
  );
}

export async function getFileStatus(
  collectionName: string,
  method = "auto",
): Promise<FileStatusResponse> {
  let response: Response;

  try {
    response = await fetch(
      `${API_BASE}/file/${encodeURIComponent(collectionName)}/status?method=${encodeURIComponent(method)}`,
      { method: "GET" },
    );
  } catch (error) {
    throw toNetworkError(error);
  }

  if (response.ok) {
    return (await response.json()) as FileStatusResponse;
  }

  const detail = await readErrorDetail(response);

  if (response.status === 404) {
    throw new FileServiceError(
      "NOT_FOUND",
      detail || "找不到對應檔案狀態",
      response.status,
    );
  }

  throw new FileServiceError(
    "SERVER",
    detail || `讀取檔案狀態失敗（HTTP ${response.status}）`,
    response.status,
  );
}
