import { useCallback, useEffect, useState } from "react";

import { getFileStatus, isFileServiceError } from "../services/fileService";
import { useIndexStore } from "../stores/useIndexStore";
import { useToastStore } from "../stores/useToastStore";
import { OverwriteConfirmDialog } from "./OverwriteConfirmDialog.tsx";

interface IndexCheckBarProps {
  collectionName: string;
}

export function IndexCheckBar({ collectionName }: IndexCheckBarProps) {
  const [isIndexed, setIsIndexed] = useState<boolean | null>(null);
  const [isParsed, setIsParsed] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  const addToast = useToastStore((state) => state.addToast);
  const indexStatus = useIndexStore((state) => state.status);
  const startIndex = useIndexStore((state) => state.startIndex);
  const confirmIndexOverwrite = useIndexStore((state) => state.confirmOverwrite);
  const cancelIndexOverwrite = useIndexStore((state) => state.cancelOverwrite);

  const isIndexing =
    indexStatus === "checking" ||
    indexStatus === "awaitingConfirm" ||
    indexStatus === "indexing";

  const checkStatus = useCallback(async () => {
    setIsChecking(true);
    try {
      const status = await getFileStatus(collectionName);
      setIsIndexed(status.is_indexed);
      setIsParsed(status.is_parsed);
    } catch (err) {
      if (isFileServiceError(err)) {
        addToast("error", err.message);
      }
      setIsIndexed(null);
      setIsParsed(null);
    } finally {
      setIsChecking(false);
    }
  }, [collectionName, addToast]);

  useEffect(() => {
    void checkStatus();
  }, [checkStatus]);

  // Re-check after indexing finishes
  useEffect(() => {
    if (indexStatus === "done") void checkStatus();
  }, [indexStatus, checkStatus]);

  if (isChecking) {
    return <span className="index-check-hint">確認索引狀態...</span>;
  }

  if (isIndexed === true) {
    return <span className="index-badge index-badge-done">已索引 ✓</span>;
  }

  if (isParsed === false) {
    return <span className="index-check-hint">尚未解析，無法索引</span>;
  }

  return (
    <>
      <button
        type="button"
        className="btn btn-primary"
        disabled={isIndexing}
        onClick={() => void startIndex(collectionName)}
      >
        {isIndexing ? "索引中..." : "建立索引"}
      </button>
      <OverwriteConfirmDialog
        open={indexStatus === "awaitingConfirm"}
        title="覆寫索引"
        message="該檔案已有索引結果，重新索引將覆寫現有內容。確定要繼續嗎？"
        onCancel={cancelIndexOverwrite}
        onConfirm={confirmIndexOverwrite}
      />
    </>
  );
}
