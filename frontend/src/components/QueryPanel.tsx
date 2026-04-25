import { useCallback, useEffect, useRef, useState } from "react";

import {
  deriveCollectionName,
  getFileStatus,
  isFileServiceError,
  listPdfs,
  type PdfFileItem,
} from "../services/fileService";
import { useQueryStore } from "../stores/useQueryStore";
import { useToastStore } from "../stores/useToastStore";

const INTERRUPTED_AT_LABELS: Record<string, string> = {
  before_sources: "檢索前",
  after_sources: "檢索後",
  during_delta: "生成中",
};

export function QueryPanel() {
  const [files, setFiles] = useState<PdfFileItem[]>([]);
  const [selectedCollection, setSelectedCollection] = useState("");
  const [question, setQuestion] = useState("");
  const [isFileListLoading, setIsFileListLoading] = useState(false);

  const addToast = useToastStore((state) => state.addToast);
  const status = useQueryStore((state) => state.status);
  const sources = useQueryStore((state) => state.sources);
  const answer = useQueryStore((state) => state.answer);
  const interruptedAt = useQueryStore((state) => state.interruptedAt);
  const errorMessage = useQueryStore((state) => state.errorMessage);
  const result = useQueryStore((state) => state.result);
  const submitQuery = useQueryStore((state) => state.submitQuery);
  const reset = useQueryStore((state) => state.reset);

  const isBusy =
    status === "checking" || status === "retrieving" || status === "generating";

  const canSubmit = question.trim().length > 0 && selectedCollection !== "" && !isBusy;

  const loadFiles = useCallback(async () => {
    setIsFileListLoading(true);
    try {
      const list = await listPdfs();
      setFiles(list);
    } catch (error) {
      const message = error instanceof Error ? error.message : "讀取檔案列表失敗";
      addToast("error", message);
    } finally {
      setIsFileListLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  const handleSelectChange = useCallback(
    async (value: string) => {
      setSelectedCollection(value);
      if (!value) return;

      try {
        const fileStatus = await getFileStatus(value);
        if (fileStatus.stage !== "indexed") {
          addToast("warning", "該檔案尚未建立索引，請先到左側執行索引");
          setSelectedCollection("");
        }
      } catch (error) {
        if (isFileServiceError(error)) {
          addToast("error", error.message);
        } else {
          addToast("error", "讀取檔案狀態失敗");
        }
        setSelectedCollection("");
      }
    },
    [addToast],
  );

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;
    void submitQuery(question, selectedCollection);
  }, [canSubmit, question, selectedCollection, submitQuery]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && event.ctrlKey) {
        event.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleReset = useCallback(() => {
    reset();
    setQuestion("");
  }, [reset]);

  const answerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (answerRef.current && answer) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight;
    }
  }, [answer]);

  const submitLabel = (() => {
    if (status === "checking") return "確認中...";
    if (status === "retrieving") return "檢索中...";
    if (status === "generating") return "生成中...";
    return "送出問題";
  })();

  return (
    <div className="query-panel">
      <h2 className="panel-title">問答查詢</h2>

      <div className="query-section">
        <label className="query-label" htmlFor="query-file-select">
          選擇檔案
        </label>
        {isFileListLoading ? (
          <p className="query-hint">載入檔案中...</p>
        ) : (
          <select
            id="query-file-select"
            className="query-select"
            value={selectedCollection}
            onChange={(e) => {
              void handleSelectChange(e.target.value);
            }}
            disabled={isBusy}
          >
            <option value="">— 選擇 PDF 檔案 —</option>
            {files.map((file) => (
              <option key={file.path} value={deriveCollectionName(file.name)}>
                {file.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="query-section">
        <label className="query-label" htmlFor="query-question">
          輸入問題
        </label>
        <textarea
          id="query-question"
          className="query-textarea"
          rows={3}
          placeholder="輸入問題，Ctrl+Enter 送出"
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
          }}
          onKeyDown={handleKeyDown}
          disabled={isBusy}
        />
        <div className="query-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {submitLabel}
          </button>
          {status !== "idle" && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={isBusy}
              onClick={handleReset}
            >
              重置
            </button>
          )}
        </div>
      </div>

      {sources.length > 0 && (
        <div className="query-section">
          <p className="query-label">檢索來源 ({sources.length})</p>
          <div className="query-sources">
            {sources.map((src) => (
              <div key={src.chunk_id} className="query-source-item">
                <p className="query-source-title">
                  {src.section_title || "（無標題）"}
                  <span className="query-source-page">第 {src.page_idx + 1} 頁</span>
                </p>
                <p className="query-source-text">
                  {src.text.length > 120 ? `${src.text.slice(0, 120)}…` : src.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {(answer || status === "retrieving") && (
        <div className="query-section">
          <p className="query-label">答案</p>
          <div
            ref={answerRef}
            className={`query-answer${status === "generating" ? " query-answer-generating" : ""}`}
          >
            {status === "retrieving" && !answer ? (
              <span className="query-hint">檢索中...</span>
            ) : (
              answer
            )}
          </div>
          {result && (
            <p className="query-hint">耗時 {result.processing_time.toFixed(2)} 秒</p>
          )}
          {status === "error" && errorMessage && (
            <div className="query-error-banner">
              <strong>錯誤：</strong>{errorMessage}
              {interruptedAt && (
                <span>（於 {INTERRUPTED_AT_LABELS[interruptedAt] ?? interruptedAt} 階段中斷）</span>
              )}
            </div>
          )}
        </div>
      )}

      {status === "error" && !answer && errorMessage && (
        <div className="query-section">
          <div className="query-error-banner">
            <strong>錯誤：</strong>{errorMessage}
            {interruptedAt && (
              <span>（於 {INTERRUPTED_AT_LABELS[interruptedAt] ?? interruptedAt} 階段中斷）</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
