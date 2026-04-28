import { useCallback, useEffect, useState } from "react";

import { listPdfs, type PdfFileItem } from "../services/fileService";
import { useToastStore } from "../stores/useToastStore";

interface FileListPanelProps {
  selectedCollection: string | null;
  onSelect: (file: PdfFileItem) => void;
  refreshTrigger?: number;
}

export function FileListPanel({ selectedCollection, onSelect, refreshTrigger }: FileListPanelProps) {
  const [files, setFiles] = useState<PdfFileItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const addToast = useToastStore((state) => state.addToast);

  const refreshFiles = useCallback(async () => {
    try {
      setFiles(await listPdfs());
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "讀取檔案失敗");
    }
  }, [addToast]);

  useEffect(() => {
    let isMounted = true;
    const initialize = async () => {
      try {
        const next = await listPdfs();
        if (isMounted) setFiles(next);
      } catch (error) {
        if (isMounted) addToast("error", error instanceof Error ? error.message : "讀取檔案失敗");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    void initialize();
    return () => { isMounted = false; };
  }, [addToast]);

  useEffect(() => {
    if (!refreshTrigger) return;
    void refreshFiles();
  }, [refreshTrigger, refreshFiles]);

  if (isLoading) return <p className="file-list-hint">讀取檔案中...</p>;
  if (files.length === 0) return <p className="file-list-hint">目前沒有 PDF，請先上傳檔案。</p>;

  return (
    <div className="file-list">
      {files.map((file) => (
        <div
          key={file.collection_name}
          className={`file-list-item${selectedCollection === file.collection_name ? " file-list-item-selected" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => onSelect(file)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onSelect(file);
            }
          }}
        >
          <span className="file-name">{file.pdf_name}</span>
        </div>
      ))}
    </div>
  );
}
