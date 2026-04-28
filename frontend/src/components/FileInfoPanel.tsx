import { useCallback, useEffect, useRef, useState } from "react";

import {
  deleteArtifact,
  deletePdf,
  getFileStatus,
  type FileStatusResponse,
  type PdfFileItem,
} from "../services/fileService";
import { useIndexStore } from "../stores/useIndexStore";
import { useParseStore } from "../stores/useParseStore";
import { useToastStore } from "../stores/useToastStore";
import { useTranslateStore } from "../stores/useTranslateStore";
import { ConfirmDialog } from "./ConfirmDialog";
import { OverwriteConfirmDialog } from "./OverwriteConfirmDialog.tsx";
import { ProgressBar } from "./ProgressBar";

interface FileInfoPanelProps {
  selectedFile: PdfFileItem | null;
  onDeleteSuccess: () => void;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function StatusBadge({ activeLabel, inactiveLabel, active }: { activeLabel: string; inactiveLabel: string; active: boolean }) {
  return (
    <span className={`status-badge ${active ? "status-badge-on" : "status-badge-off"}`}>
      {active ? activeLabel : inactiveLabel}
    </span>
  );
}

export function FileInfoPanel({ selectedFile, onDeleteSuccess }: FileInfoPanelProps) {
  const [fileStatus, setFileStatus] = useState<FileStatusResponse | null>(null);
  const [isStatusLoading, setIsStatusLoading] = useState(false);
  const [isWorking, setIsWorking] = useState(false);
  const [showDeleteFile, setShowDeleteFile] = useState(false);
  const [showDeleteArtifact, setShowDeleteArtifact] = useState(false);
  const [displayStatus, setDisplayStatus] = useState<{
    title: string;
    main: string;
    subs: string[];
    isError: boolean;
  } | null>(null);

  const addToast = useToastStore((state) => state.addToast);

  const parseStatus = useParseStore((state) => state.status);
  const parsePercent = useParseStore((state) => state.percent);
  const parseMessage = useParseStore((state) => state.message);
  const parseResult = useParseStore((state) => state.result);
  const parseError = useParseStore((state) => state.errorMessage);
  const startParse = useParseStore((state) => state.startParse);
  const confirmParseOverwrite = useParseStore((state) => state.confirmOverwrite);
  const cancelParseOverwrite = useParseStore((state) => state.cancelOverwrite);

  const translateStatus = useTranslateStore((state) => state.status);
  const translatePercent = useTranslateStore((state) => state.percent);
  const translateMessage = useTranslateStore((state) => state.message);
  const translateResult = useTranslateStore((state) => state.result);
  const translateError = useTranslateStore((state) => state.errorMessage);
  const startTranslate = useTranslateStore((state) => state.startTranslate);
  const confirmOverwrite = useTranslateStore((state) => state.confirmOverwrite);
  const cancelOverwrite = useTranslateStore((state) => state.cancelOverwrite);

  const indexStatus = useIndexStore((state) => state.status);
  const indexPercent = useIndexStore((state) => state.percent);
  const indexMessage = useIndexStore((state) => state.message);
  const indexResult = useIndexStore((state) => state.result);
  const indexCollection = useIndexStore((state) => state.collectionName);
  const indexError = useIndexStore((state) => state.errorMessage);
  const startIndex = useIndexStore((state) => state.startIndex);
  const confirmIndexOverwrite = useIndexStore((state) => state.confirmOverwrite);
  const cancelIndexOverwrite = useIndexStore((state) => state.cancelOverwrite);

  const prevParseStatus = useRef(parseStatus);
  const prevTranslateStatus = useRef(translateStatus);
  const prevIndexStatus = useRef(indexStatus);

  const isParsing =
    parseStatus === "checking" ||
    parseStatus === "awaitingConfirm" ||
    parseStatus === "parsing";
  const isTranslating =
    translateStatus === "checking" ||
    translateStatus === "awaitingConfirm" ||
    translateStatus === "translating";
  const isIndexing =
    indexStatus === "checking" ||
    indexStatus === "awaitingConfirm" ||
    indexStatus === "indexing";
  const isBusy = isWorking || isParsing || isTranslating || isIndexing;

  const refreshStatus = useCallback(async (collectionName: string) => {
    setIsStatusLoading(true);
    try {
      setFileStatus(await getFileStatus(collectionName));
    } catch {
      setFileStatus(null);
    } finally {
      setIsStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedFile) {
      setFileStatus(null);
      setDisplayStatus(null);
      return;
    }
    void refreshStatus(selectedFile.collection_name);
  }, [selectedFile, refreshStatus]);

  // Refresh status badges after each stage completes
  useEffect(() => {
    if (!selectedFile) return;
    const parseDone = parseStatus === "done" && prevParseStatus.current !== "done";
    const translateDone = translateStatus === "done" && prevTranslateStatus.current !== "done";
    const indexDone = indexStatus === "done" && prevIndexStatus.current !== "done";

    if (parseDone || translateDone || indexDone) {
      void refreshStatus(selectedFile.collection_name);
    }
  }, [parseStatus, translateStatus, indexStatus, selectedFile, refreshStatus]);

  useEffect(() => {
    if (parseStatus !== prevParseStatus.current && (parseStatus === "done" || parseStatus === "error")) {
      const isErr = parseStatus === "error";
      setDisplayStatus({
        title: "解析狀態",
        main: isErr ? "解析失敗" : "解析完成",
        subs: isErr
          ? [parseError ?? "發生未知錯誤"]
          : [`耗時 ${parseResult?.processing_time.toFixed(2) ?? "0.00"} 秒`],
        isError: isErr,
      });
    }

    if (translateStatus !== prevTranslateStatus.current && (translateStatus === "done" || translateStatus === "error")) {
      const isErr = translateStatus === "error";
      setDisplayStatus({
        title: "翻譯狀態",
        main: isErr ? "翻譯失敗" : "翻譯完成",
        subs: isErr
          ? [translateError ?? "發生未知錯誤"]
          : [
              `已翻譯 ${translateResult?.translated_count ?? 0} 段`,
              `已跳過 ${translateResult?.skipped_count ?? 0} 段`,
              `耗時 ${translateResult?.processing_time.toFixed(2) ?? "0.00"} 秒`,
            ],
        isError: isErr,
      });
    }

    if (indexStatus !== prevIndexStatus.current && (indexStatus === "done" || indexStatus === "error")) {
      const isErr = indexStatus === "error";
      setDisplayStatus({
        title: "索引狀態",
        main: isErr ? "索引失敗" : "索引完成",
        subs: isErr
          ? [indexError ?? "發生未知錯誤"]
          : [
              `collection: ${indexCollection ?? "-"}`,
              `切分 ${indexResult?.chunk_count ?? 0} 個 chunk，耗時 ${indexResult?.processing_time.toFixed(2) ?? "0.00"} 秒`,
            ],
        isError: isErr,
      });
    }

    prevParseStatus.current = parseStatus;
    prevTranslateStatus.current = translateStatus;
    prevIndexStatus.current = indexStatus;
  }, [
    parseStatus,
    parseResult,
    parseError,
    translateStatus,
    translateResult,
    translateError,
    indexStatus,
    indexResult,
    indexCollection,
    indexError,
  ]);

  const handleDeleteFile = useCallback(async () => {
    if (!selectedFile) return;
    setIsWorking(true);
    try {
      await deletePdf(selectedFile.pdf_name);
      addToast("success", `已刪除 ${selectedFile.pdf_name}`);
      onDeleteSuccess();
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "刪除失敗");
    } finally {
      setIsWorking(false);
      setShowDeleteFile(false);
    }
  }, [selectedFile, addToast, onDeleteSuccess]);

  const handleDeleteArtifact = useCallback(async () => {
    if (!selectedFile) return;
    setIsWorking(true);
    try {
      await deleteArtifact(selectedFile.collection_name);
      addToast("success", `已刪除 ${selectedFile.pdf_name} 的輸出`);
      if (selectedFile) void refreshStatus(selectedFile.collection_name);
    } catch (error) {
      addToast("error", error instanceof Error ? error.message : "刪除輸出失敗");
    } finally {
      setIsWorking(false);
      setShowDeleteArtifact(false);
    }
  }, [selectedFile, addToast, refreshStatus]);

  if (!selectedFile) {
    return (
      <div className="file-info-panel file-info-empty">
        <p>請在左側選擇一個檔案。</p>
      </div>
    );
  }

  return (
    <div className="file-info-panel">
      <div className="file-info-header">
        <h3 className="file-info-name" title={selectedFile.pdf_name}>
          {selectedFile.pdf_name}
        </h3>
        {selectedFile.upload_date && (
          <p className="file-info-date">上傳於 {formatDate(selectedFile.upload_date)}</p>
        )}
      </div>

      <hr className="file-info-divider" />

      <div className="file-info-section">
        <p className="file-info-section-title">處理狀態</p>
        <div className="file-info-status">
          {isStatusLoading ? (
            <span className="file-info-hint">確認狀態中...</span>
          ) : fileStatus ? (
            <>
              <StatusBadge activeLabel="已解析" inactiveLabel="未解析" active={fileStatus.is_parsed} />
              <StatusBadge activeLabel="已翻譯" inactiveLabel="未翻譯" active={fileStatus.is_translated} />
              <StatusBadge activeLabel="已索引" inactiveLabel="未索引" active={fileStatus.is_indexed} />
            </>
          ) : null}
        </div>
      </div>

      <hr className="file-info-divider" />

      <div className="file-info-section">
        <p className="file-info-section-title">操作</p>
        <div className="file-info-actions">
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={isBusy}
            onClick={() => void startParse(selectedFile.collection_name)}
          >
            {isParsing ? "解析中..." : "解析"}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={isBusy}
            onClick={() => void startTranslate(selectedFile.collection_name)}
          >
            {isTranslating ? "翻譯中..." : "翻譯"}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={isBusy}
            onClick={() => void startIndex(selectedFile.collection_name)}
          >
            {isIndexing ? "索引中..." : "索引"}
          </button>
        </div>
      </div>

      <hr className="file-info-divider" />

      <div className="file-info-section">
        <p className="file-info-section-title">刪除</p>
        <div className="file-info-actions">
          <button
            type="button"
            className="btn btn-secondary btn-block"
            disabled={isBusy}
            onClick={() => setShowDeleteArtifact(true)}
          >
            刪除輸出
          </button>
          <button
            type="button"
            className="btn btn-danger btn-block"
            disabled={isBusy}
            onClick={() => setShowDeleteFile(true)}
          >
            刪除原檔
          </button>
        </div>
      </div>

      <hr className="file-info-divider" />

      {(() => {
        const activeOp =
          indexStatus === "checking" || indexStatus === "awaitingConfirm" || indexStatus === "indexing" ? "index" :
          translateStatus === "checking" || translateStatus === "awaitingConfirm" || translateStatus === "translating" ? "translate" :
          parseStatus === "checking" || parseStatus === "awaitingConfirm" || parseStatus === "parsing" ? "parse" : null;

        if (activeOp === "index") {
          return (
            <section className="parse-status" aria-live="polite">
              <h2 className="panel-title">索引狀態</h2>
              {indexStatus === "checking" && <p className="parse-main">正在確認檔案狀態...</p>}
              {indexStatus === "awaitingConfirm" && <p className="parse-main">等待覆寫確認</p>}
              {indexStatus === "indexing" && (
                <>
                  <p className="parse-main">索引中...</p>
                  <ProgressBar percent={indexPercent} message={indexMessage || "處理中"} />
                </>
              )}
            </section>
          );
        }

        if (activeOp === "translate") {
          return (
            <section className="parse-status" aria-live="polite">
              <h2 className="panel-title">翻譯狀態</h2>
              {translateStatus === "checking" && <p className="parse-main">正在確認檔案狀態...</p>}
              {translateStatus === "awaitingConfirm" && (
                <>
                  <p className="parse-main">等待覆寫確認</p>
                  <p className="parse-sub">{selectedFile.pdf_name}</p>
                </>
              )}
              {translateStatus === "translating" && (
                <>
                  <p className="parse-main">翻譯中... {selectedFile.pdf_name}</p>
                  <ProgressBar percent={translatePercent} message={translateMessage || "處理中"} />
                </>
              )}
            </section>
          );
        }

        if (activeOp === "parse") {
          return (
            <section className="parse-status" aria-live="polite">
              <h2 className="panel-title">解析狀態</h2>
              {parseStatus === "checking" && <p className="parse-main">正在確認檔案狀態...</p>}
              {parseStatus === "awaitingConfirm" && <p className="parse-main">等待覆寫確認</p>}
              {parseStatus === "parsing" && (
                <ProgressBar percent={parsePercent} message={parseMessage || "處理中"} />
              )}
            </section>
          );
        }

        if (!displayStatus) return null;

        return (
          <section
            className={`parse-status${displayStatus.isError ? " parse-status-error" : ""}`}
            aria-live="polite"
          >
            <h2 className="panel-title">{displayStatus.title}</h2>
            <p className="parse-main">{displayStatus.main}</p>
            {displayStatus.subs.map((text, index) => (
              <p key={`${displayStatus.title}-${index}`} className="parse-sub">
                {text}
              </p>
            ))}
          </section>
        );
      })()}

      <ConfirmDialog
        open={showDeleteFile}
        title="刪除檔案"
        message={`確定要刪除 ${selectedFile.pdf_name} 嗎？此操作無法復原。`}
        onCancel={() => setShowDeleteFile(false)}
        onConfirm={() => void handleDeleteFile()}
      />
      <ConfirmDialog
        open={showDeleteArtifact}
        title="刪除輸出"
        message={`確定要刪除 ${selectedFile.pdf_name} 的所有輸出資料嗎？此操作無法復原。`}
        onCancel={() => setShowDeleteArtifact(false)}
        onConfirm={() => void handleDeleteArtifact()}
      />
      <OverwriteConfirmDialog
        open={translateStatus === "awaitingConfirm"}
        title="覆寫翻譯"
        message="該檔案已有翻譯結果，重新翻譯將覆寫現有內容。確定要繼續嗎？"
        onCancel={cancelOverwrite}
        onConfirm={confirmOverwrite}
      />
      <OverwriteConfirmDialog
        open={parseStatus === "awaitingConfirm"}
        title="覆寫解析"
        message="該檔案已有解析結果，重新解析將覆寫現有內容。確定要繼續嗎？"
        onCancel={cancelParseOverwrite}
        onConfirm={confirmParseOverwrite}
      />
      <OverwriteConfirmDialog
        open={indexStatus === "awaitingConfirm"}
        title="覆寫索引"
        message="該檔案已有索引結果，重新索引將覆寫現有內容。確定要繼續嗎？"
        onCancel={cancelIndexOverwrite}
        onConfirm={confirmIndexOverwrite}
      />
    </div>
  );
}
