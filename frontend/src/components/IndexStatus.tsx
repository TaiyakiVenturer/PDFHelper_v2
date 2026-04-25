import { ProgressBar } from "./ProgressBar";
import { useIndexStore } from "../stores/useIndexStore";

export function IndexStatus() {
  const status = useIndexStore((state) => state.status);
  const percent = useIndexStore((state) => state.percent);
  const message = useIndexStore((state) => state.message);
  const result = useIndexStore((state) => state.result);
  const errorMessage = useIndexStore((state) => state.errorMessage);

  if (status === "idle") {
    return null;
  }

  if (status === "checking") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">索引狀態</h2>
        <p className="parse-main">正在確認檔案狀態...</p>
      </section>
    );
  }

  if (status === "indexing") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">索引狀態</h2>
        <p className="parse-main">索引中...</p>
        <ProgressBar percent={percent} message={message || "處理中"} />
      </section>
    );
  }

  if (status === "done") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">索引狀態</h2>
        <p className="parse-main">索引完成</p>
        <p className="parse-sub">collection: {result?.collection_name ?? "-"}</p>
        <p className="parse-sub">
          切分 {result?.chunk_count ?? 0} 個 chunk，耗時{" "}
          {result?.processing_time.toFixed(2) ?? "0.00"} 秒
        </p>
      </section>
    );
  }

  return (
    <section className="parse-status parse-status-error" aria-live="assertive">
      <h2 className="panel-title">索引狀態</h2>
      <p className="parse-main">索引失敗</p>
      <p className="parse-sub">{errorMessage ?? "發生未知錯誤"}</p>
    </section>
  );
}
