import { useCallback, useEffect, useState } from "react";

import { DualMarkdownPane } from "../components/DualMarkdownPane";
import { IndexCheckBar } from "../components/IndexCheckBar";
import { QueryPanel } from "../components/QueryPanel";
import { listPdfs, type PdfFileItem } from "../services/fileService";
import { useToastStore } from "../stores/useToastStore";

export function QueryPage() {
  const [files, setFiles] = useState<PdfFileItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [queryOpen, setQueryOpen] = useState(false);

  const addToast = useToastStore((state) => state.addToast);

  const loadFiles = useCallback(async () => {
    setIsLoading(true);
    try {
      setFiles(await listPdfs());
    } catch (err) {
      addToast("error", err instanceof Error ? err.message : "讀取檔案列表失敗");
    } finally {
      setIsLoading(false);
    }
  }, [addToast]);

  useEffect(() => { void loadFiles(); }, [loadFiles]);

  return (
    <div className="query-page">
      <div className="query-page-toolbar panel">
        <label className="query-label" htmlFor="qp-file-select">檔案</label>
        {isLoading ? (
          <span className="query-hint">載入中...</span>
        ) : (
          <select
            id="qp-file-select"
            className="query-select query-select-toolbar"
            value={selected ?? ""}
            onChange={(e) => setSelected(e.target.value || null)}
          >
            <option value="">— 選擇 PDF 檔案 —</option>
            {files.map((f) => (
              <option key={f.collection_name} value={f.collection_name}>
                {f.pdf_name}
              </option>
            ))}
          </select>
        )}
        {selected && <IndexCheckBar collectionName={selected} />}
        <button
          type="button"
          className={`btn query-toggle-btn${queryOpen ? " btn-primary" : " btn-secondary"}`}
          onClick={() => setQueryOpen((o) => !o)}
        >
          {queryOpen ? "關閉查詢" : "開啟查詢"}
        </button>
      </div>

      <div className={`query-page-body${queryOpen ? " query-sidebar-open" : ""}`}>
        <DualMarkdownPane collectionName={selected} />
      </div>
      <div
        className={`panel query-page-sidebar${queryOpen ? " is-open" : ""}`}
        aria-hidden={!queryOpen}
      >
        <QueryPanel collectionName={selected} />
      </div>
    </div>
  );
}
