import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { useCallback, useEffect, useRef, useState } from "react";

import { copyPdfToDataDir, isFileServiceError } from "../services/fileService";
import { useParseStore } from "../stores/useParseStore";
import { useToastStore } from "../stores/useToastStore";

function getFilenameFromPath(path: string): string {
  const normalized = path.trim();
  if (!normalized) return "";
  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || normalized;
}

interface UploadDropZoneProps {
  onUploadSuccess: () => void;
  fullPage?: boolean;
}

export function UploadDropZone({ onUploadSuccess, fullPage }: UploadDropZoneProps) {
  const [isWorking, setIsWorking] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [pendingName, setPendingName] = useState<string | null>(null);

  const addToast = useToastStore((state) => state.addToast);
  const isParsing = useParseStore((state) => state.status) === "parsing";

  const isDisabled = isWorking || isParsing;

  const clearPending = useCallback(() => {
    setPendingPath(null);
    setPendingName(null);
  }, []);

  const setPendingFromPath = useCallback(
    (sourcePath: string) => {
      const normalized = sourcePath.trim();
      if (!normalized) {
        addToast("error", "無法取得檔案路徑");
        return;
      }
      setPendingPath(normalized);
      setPendingName(getFilenameFromPath(normalized));
    },
    [addToast],
  );

  const uploadFromPath = useCallback(
    async (sourcePath: string): Promise<boolean> => {
      setIsWorking(true);
      try {
        const uploaded = await copyPdfToDataDir(sourcePath);
        addToast("success", `已上傳 ${uploaded.pdf_name}`);
        onUploadSuccess();
        return true;
      } catch (error) {
        if (isFileServiceError(error)) {
          if (error.code === "CONFLICT" || error.code === "BAD_REQUEST") {
            addToast("warning", error.message);
          } else {
            addToast("error", error.message);
          }
        } else {
          addToast("error", error instanceof Error ? error.message : "上傳失敗");
        }
        return false;
      } finally {
        setIsWorking(false);
      }
    },
    [addToast, onUploadSuccess],
  );

  const uploadFromPathRef = useRef(uploadFromPath);
  const setPendingFromPathRef = useRef(setPendingFromPath);
  const addToastRef = useRef(addToast);

  useEffect(() => { uploadFromPathRef.current = uploadFromPath; }, [uploadFromPath]);
  useEffect(() => { setPendingFromPathRef.current = setPendingFromPath; }, [setPendingFromPath]);
  useEffect(() => { addToastRef.current = addToast; }, [addToast]);

  const pickFileWithDialog = useCallback(async () => {
    const selected = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    });
    if (typeof selected !== "string") return;
    setPendingFromPath(selected);
  }, [setPendingFromPath]);

  const handleUploadPending = useCallback(async () => {
    if (!pendingPath) return;
    const succeeded = await uploadFromPath(pendingPath);
    if (succeeded) clearPending();
  }, [clearPending, pendingPath, uploadFromPath]);

  useEffect(() => {
    let disposed = false;
    const unlisteners: Array<() => void> = [];

    const setupListeners = async () => {
      const unlistenDrop = await listen<{ paths: string[] }>("tauri://drag-drop", (event) => {
        setIsDragOver(false);
        const paths = event.payload.paths;
        if (paths.length === 0) return;
        if (paths.length > 1) {
          addToastRef.current("warning", "一次僅支援拖曳單一 PDF，將處理第一個檔案", 4000);
        }
        setPendingFromPathRef.current(paths[0]);
      });
      if (disposed) { unlistenDrop(); return; }
      unlisteners.push(unlistenDrop);

      const unlistenEnter = await listen("tauri://drag-enter", () => setIsDragOver(true));
      if (disposed) { unlistenEnter(); return; }
      unlisteners.push(unlistenEnter);

      const unlistenLeave = await listen("tauri://drag-leave", () => setIsDragOver(false));
      if (disposed) { unlistenLeave(); return; }
      unlisteners.push(unlistenLeave);
    };

    void setupListeners();

    return () => {
      disposed = true;
      unlisteners.forEach((u) => u());
    };
  }, []);

  return (
    <div
      className={[
        "drop-zone",
        isDragOver ? "drop-zone-active" : "",
        isDisabled ? "drop-zone-disabled" : "",
        fullPage ? "drop-zone-full-page" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="button"
      aria-disabled={isDisabled}
      tabIndex={isDisabled ? -1 : 0}
      onClick={() => {
        if (isDisabled) return;
        void pickFileWithDialog();
      }}
      onKeyDown={(e) => {
        if (isDisabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          void pickFileWithDialog();
        }
      }}
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={(e) => { e.preventDefault(); setIsDragOver(false); }}
      onDrop={(e) => { e.preventDefault(); setIsDragOver(false); }}
    >
      <p>拖曳 PDF 到這裡，或點擊此區域選擇檔案</p>

      {pendingPath ? (
        <div className="pending-upload-card">
          <p className="pending-upload-name">{pendingName ?? "未命名檔案"}</p>
          <p className="pending-upload-path" title={pendingPath}>{pendingPath}</p>
          {!isDisabled && (
            <div className="pending-upload-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={(e) => { e.stopPropagation(); void handleUploadPending(); }}
              >
                上傳
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={(e) => { e.stopPropagation(); clearPending(); }}
              >
                取消
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
