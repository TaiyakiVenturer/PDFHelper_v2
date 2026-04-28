import { memo, useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

import "katex/dist/katex.min.css";

import { getMarkdownContent, isFileServiceError } from "../services/fileService";

interface MarkdownViewerProps {
  collectionName: string | null;
  version: "original" | "translated";
  title: string;
}

export const MarkdownViewer = memo(function MarkdownViewer({
  collectionName,
  version,
  title,
}: MarkdownViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [renderContent, setRenderContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!collectionName) {
      setContent(null);
      setRenderContent(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setContent(null);
    setRenderContent(null);

    getMarkdownContent(collectionName, version)
      .then((text) => {
        if (!cancelled) setContent(text);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setContent(null);
        if (isFileServiceError(err) && err.code === "NOT_FOUND") {
          setError("尚無此版本文件");
        } else {
          setError(err instanceof Error ? err.message : "載入失敗");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => { cancelled = true; };
  }, [collectionName, version, tick]);

  useEffect(() => {
    if (content === null) {
      setRenderContent(null);
      return;
    }

    let cancelled = false;

    const requestIdle = (cb: () => void): number => {
      const idle = (globalThis as { requestIdleCallback?: (fn: () => void) => number }).requestIdleCallback;
      if (typeof idle === "function") {
        return idle(cb);
      }
      return globalThis.setTimeout(cb, 16);
    };

    const cancelIdle = (handle: number): void => {
      const cancel = (globalThis as { cancelIdleCallback?: (id: number) => void }).cancelIdleCallback;
      if (typeof cancel === "function") {
        cancel(handle);
      } else {
        globalThis.clearTimeout(handle);
      }
    };

    const handle = requestIdle(() => {
      if (cancelled) return;
      setRenderContent(content);
    });

    return () => {
      cancelled = true;
      cancelIdle(handle);
    };
  }, [content]);

  return (
    <div className="markdown-viewer">
      <div className="markdown-viewer-header">
        <span>{title}</span>
        {collectionName && !isLoading && (
          <button type="button" className="markdown-reload-btn" onClick={reload} title="重新載入">
            ↺
          </button>
        )}
      </div>
      <div className="markdown-viewer-body">
        {isLoading && <p className="markdown-placeholder">載入中...</p>}
        {!isLoading && error && (
          <p className="markdown-placeholder markdown-error">{error}</p>
        )}
        {!isLoading && !error && content === null && (
          <p className="markdown-placeholder">請先選擇檔案。</p>
        )}
        {!isLoading && !error && content !== null && renderContent === null && (
          <p className="markdown-placeholder">渲染中...</p>
        )}
        {!isLoading && !error && renderContent !== null && (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeRaw, rehypeKatex]}
          >
            {renderContent}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
});
