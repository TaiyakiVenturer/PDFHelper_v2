import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

import "katex/dist/katex.min.css";

import { useQueryStore } from "../stores/useQueryStore";

const INTERRUPTED_AT_LABELS: Record<string, string> = {
  before_sources: "檢索前",
  after_sources: "檢索後",
  during_delta: "生成中",
};

interface QueryPanelProps {
  collectionName: string | null;
}

export function QueryPanel({ collectionName }: QueryPanelProps) {
  const [question, setQuestion] = useState("");

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

  const canSubmit = question.trim().length > 0 && collectionName !== null && !isBusy;

  const handleSubmit = useCallback(() => {
    if (!canSubmit || !collectionName) return;
    void submitQuery(question, collectionName);
  }, [canSubmit, collectionName, question, submitQuery]);

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

  if (!collectionName) {
    return (
      <div className="query-panel">
        <h2 className="panel-title">問答查詢</h2>
        <p className="query-hint">請先在左側選擇一份 PDF 檔案。</p>
      </div>
    );
  }

  return (
    <div className="query-panel">
      <h2 className="panel-title">問答查詢</h2>

      <div className="query-section">
        <label className="query-label" htmlFor="query-question">
          輸入問題
        </label>
        <textarea
          id="query-question"
          className="query-textarea"
          rows={3}
          placeholder="輸入問題，Ctrl+Enter 送出"
          value={question ?? ""}
          onChange={(e) => setQuestion(e.target.value)}
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
              <details key={src.chunk_id} className="query-source-item">
                <summary className="query-source-summary">
                  <span className="query-source-title">
                    {src.section_title || "（無標題）"}
                  </span>
                  <span className="query-source-page">第 {src.page_idx + 1} 頁</span>
                </summary>
                <div className="query-source-detail">{src.text}</div>
              </details>
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
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeRaw, rehypeKatex]}
              >
                {answer}
              </ReactMarkdown>
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
