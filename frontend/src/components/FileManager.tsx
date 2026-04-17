import { listen } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  copyPdfToDataDir,
  deletePdf,
  isFileServiceError,
  listPdfs,
  type PdfFileItem,
} from "../services/fileService";
import { useParseStore } from "../stores/useParseStore";
import { useToastStore } from "../stores/useToastStore";
import { ConfirmDialog } from "./ConfirmDialog";

function getFilenameFromPath(path: string): string {
  const normalized = path.trim();
  if (!normalized) {
    return "";
  }

  const parts = normalized.split(/[/\\]/);
  return parts[parts.length - 1] || normalized;
}

export function FileManager() {
  const [files, setFiles] = useState<PdfFileItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PdfFileItem | null>(null);
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [pendingName, setPendingName] = useState<string | null>(null);

  const addToast = useToastStore((state) => state.addToast);
  const parseStatus = useParseStore((state) => state.status);
  const startParse = useParseStore((state) => state.startParse);

  const isParsing = parseStatus === "parsing";

  const clearPending = useCallback(() => {
    setPendingPath(null);
    setPendingName(null);
  }, []);

  const setPendingFromPath = useCallback(
    (sourcePath: string) => {
      const normalizedPath = sourcePath.trim();
      if (!normalizedPath) {
        addToast("error", "無法取得檔案路徑");
        return;
      }

      setPendingPath(normalizedPath);
      setPendingName(getFilenameFromPath(normalizedPath));
    },
    [addToast],
  );

  const refreshFiles = useCallback(async () => {
    try {
      const nextFiles = await listPdfs();
      setFiles(nextFiles);
    } catch (error) {
      const message = error instanceof Error ? error.message : "讀取檔案失敗";
      addToast("error", message);
    }
  }, [addToast]);

  useEffect(() => {
    let isMounted = true;

    const initialize = async () => {
      try {
        const nextFiles = await listPdfs();
        if (isMounted) {
          setFiles(nextFiles);
        }
      } catch (error) {
        if (isMounted) {
          const message = error instanceof Error ? error.message : "讀取檔案失敗";
          addToast("error", message);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void initialize();

    return () => {
      isMounted = false;
    };
  }, [addToast]);

  const uploadFromPath = useCallback(
    async (sourcePath: string): Promise<boolean> => {
      setIsWorking(true);

      try {
        const uploadedFile = await copyPdfToDataDir(sourcePath);
        await refreshFiles();
        addToast("success", `已上傳 ${uploadedFile.name}`);
        return true;
      } catch (error) {
        if (isFileServiceError(error)) {
          if (error.code === "CONFLICT" || error.code === "BAD_REQUEST") {
            addToast("warning", error.message);
          } else {
            addToast("error", error.message);
          }
        } else {
          const message = error instanceof Error ? error.message : "上傳失敗";
          addToast("error", message);
        }

        return false;
      } finally {
        setIsWorking(false);
      }
    },
    [addToast, refreshFiles],
  );

  const uploadFromPathRef = useRef(uploadFromPath);
  const setPendingFromPathRef = useRef(setPendingFromPath);
  const addToastRef = useRef(addToast);

  useEffect(() => {
    uploadFromPathRef.current = uploadFromPath;
  }, [uploadFromPath]);

  useEffect(() => {
    setPendingFromPathRef.current = setPendingFromPath;
  }, [setPendingFromPath]);

  useEffect(() => {
    addToastRef.current = addToast;
  }, [addToast]);

  const pickFileWithDialog = useCallback(async () => {
    const selected = await open({
      multiple: false,
      directory: false,
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    });

    if (typeof selected !== "string") {
      return;
    }

    setPendingFromPath(selected);
  }, [setPendingFromPath]);

  const handleUploadPending = useCallback(async () => {
    if (!pendingPath) {
      return;
    }

    const succeeded = await uploadFromPath(pendingPath);
    if (succeeded) {
      clearPending();
    }
  }, [clearPending, pendingPath, uploadFromPath]);

  useEffect(() => {
    let disposed = false;
    const unlisteners: Array<() => void> = [];

    const setupListeners = async () => {
      const unlistenDrop = await listen<{ paths: string[] }>("tauri://drag-drop", (event) => {
        setIsDragOver(false);

        const droppedPaths = event.payload.paths;
        if (droppedPaths.length === 0) {
          return;
        }

        if (droppedPaths.length > 1) {
          addToastRef.current("warning", "一次僅支援拖曳單一 PDF，將處理第一個檔案", 4000);
        }

        setPendingFromPathRef.current(droppedPaths[0]);
      });
      if (disposed) {
        unlistenDrop();
        return;
      }
      unlisteners.push(unlistenDrop);

      const unlistenEnter = await listen("tauri://drag-enter", () => {
        setIsDragOver(true);
      });
      if (disposed) {
        unlistenEnter();
        return;
      }
      unlisteners.push(unlistenEnter);

      const unlistenLeave = await listen("tauri://drag-leave", () => {
        setIsDragOver(false);
      });
      if (disposed) {
        unlistenLeave();
        return;
      }
      unlisteners.push(unlistenLeave);
    };

    void setupListeners();

    return () => {
      disposed = true;
      unlisteners.forEach((unlisten) => {
        unlisten();
      });
    };
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) {
      return;
    }

    setIsWorking(true);

    try {
      await deletePdf(deleteTarget.name);
      await refreshFiles();
      addToast("success", `已刪除 ${deleteTarget.name}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "刪除失敗";
      addToast("error", message);
    } finally {
      setIsWorking(false);
      setDeleteTarget(null);
    }
  }, [addToast, deleteTarget, refreshFiles]);

  return (
    <section className="file-manager">
      <h2 className="panel-title">原檔管理</h2>

      <div
        className={`drop-zone${isDragOver ? " drop-zone-active" : ""}${isWorking || isParsing ? " drop-zone-disabled" : ""}`}
        role="button"
        aria-disabled={isWorking || isParsing}
        tabIndex={isWorking || isParsing ? -1 : 0}
        onClick={() => {
          if (isWorking || isParsing) {
            return;
          }
          void pickFileWithDialog();
        }}
        onKeyDown={(event) => {
          if (isWorking || isParsing) {
            return;
          }
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            void pickFileWithDialog();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragOver(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setIsDragOver(false);
        }}
      >
        <p>拖曳 PDF 到這裡，或點擊此區域選擇檔案</p>

        {pendingPath ? (
          <div className="pending-upload-card">
            <p className="pending-upload-name">{pendingName || "未命名檔案"}</p>
            <p className="pending-upload-path" title={pendingPath}>{pendingPath}</p>
            {!isWorking && !isParsing ? (
              <div className="pending-upload-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleUploadPending();
                  }}
                >
                  上傳
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={(event) => {
                    event.stopPropagation();
                    clearPending();
                  }}
                >
                  取消
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="file-list">
        {isLoading ? (
          <p>讀取檔案中...</p>
        ) : files.length === 0 ? (
          <p>目前沒有 PDF，請先上傳檔案。</p>
        ) : (
          files.map((file) => (
            <div key={file.path} className="file-item">
              <span className="file-name">{file.name}</span>
              <div className="file-buttons">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={isWorking || isParsing}
                  onClick={() => {
                    setDeleteTarget(file);
                  }}
                >
                  刪除
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={isWorking || isParsing}
                  onClick={() => {
                    void startParse(file.path);
                  }}
                >
                  {isParsing ? "解析中..." : "開始解析"}
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="刪除檔案"
        message={
          deleteTarget
            ? `確定要刪除 ${deleteTarget.name} 嗎？此操作無法復原。`
            : ""
        }
        onCancel={() => {
          setDeleteTarget(null);
        }}
        onConfirm={() => {
          void handleDeleteConfirm();
        }}
      />
    </section>
  );
}
