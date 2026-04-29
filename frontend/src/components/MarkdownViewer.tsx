import { memo, useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";

import "katex/dist/katex.min.css";

import { getMarkdownContent, isFileServiceError } from "../services/fileService";
import { useQueryStore } from "../stores/useQueryStore";

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
  const bodyRef = useRef<HTMLDivElement>(null);

  const reload = useCallback(() => setTick((n) => n + 1), []);

  const scrollTarget = useQueryStore((state) => state.scrollTarget);
  useEffect(() => {
    if (!scrollTarget || !bodyRef.current) return;
    const body = bodyRef.current;

    const flashHighlight = (el: Element) => {
      // Invalidate any previous animation on this element via a generation counter
      const gen = (parseInt(el.getAttribute("data-hl-gen") ?? "0") + 1);
      el.setAttribute("data-hl-gen", String(gen));

      el.classList.remove("markdown-chunk-highlight-fade");
      el.classList.add("markdown-chunk-highlight");
      el.scrollIntoView({ behavior: "smooth", block: "center" });

      let settled = false;
      const startFade = () => {
        if (settled) return;
        if (parseInt(el.getAttribute("data-hl-gen") ?? "0") !== gen) return;
        settled = true;
        observer.disconnect();
        el.classList.add("markdown-chunk-highlight-fade");
        setTimeout(() => {
          if (parseInt(el.getAttribute("data-hl-gen") ?? "0") !== gen) return;
          el.classList.remove("markdown-chunk-highlight", "markdown-chunk-highlight-fade");
        }, 2000);
      };

      const observer = new IntersectionObserver(
        (entries) => { if (entries[0].isIntersecting) startFade(); },
        { root: body, threshold: 0.3 },
      );
      observer.observe(el);
      setTimeout(startFade, 1500);
    };

    // Locate the heading element matching sectionTitle (original pane only;
    // translated headings are in the target language so title won't match)
    let headingEl: Element | null = null;
    if (version === "original" && scrollTarget.sectionTitle) {
      for (const h of Array.from(body.querySelectorAll("h1,h2,h3,h4,h5,h6"))) {
        if (h.textContent?.trim() === scrollTarget.sectionTitle.trim()) {
          headingEl = h;
          break;
        }
      }
    }

    // Word-overlap matching: robust against KaTeX artifacts and split chunks.
    // Extract words ≥ 4 chars (skips single-letter KaTeX remnants like "d","s","obj").
    const wordsOf = (s: string): string[] =>
      s.replace(/[^a-z0-9\s]/gi, " ")
       .toLowerCase()
       .split(/\s+/)
       .filter((w) => w.length >= 4);

    // Find the chunk paragraph after the heading
    if (scrollTarget.chunkText) {
      const needleWords = wordsOf(scrollTarget.chunkText).slice(0, 10);
      const threshold = Math.min(5, needleWords.length);
      const FOLLOW = Node.DOCUMENT_POSITION_FOLLOWING;

      if (needleWords.length >= threshold) {
        for (const el of Array.from(body.querySelectorAll("p, li, td, blockquote, pre"))) {
          if (headingEl && !(headingEl.compareDocumentPosition(el) & FOLLOW)) continue;
          const elWords = new Set(wordsOf(el.textContent ?? ""));
          const hits = needleWords.filter((w) => elWords.has(w)).length;
          if (hits >= threshold) {
            flashHighlight(el);
            return;
          }
        }
      }
    }

    // Fallback: scroll to the heading only
    if (headingEl) {
      headingEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [scrollTarget]);

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
      <div className="markdown-viewer-body" ref={bodyRef}>
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
