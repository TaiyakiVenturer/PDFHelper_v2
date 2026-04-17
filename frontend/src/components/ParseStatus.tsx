import { useParseStore } from "../stores/useParseStore";

export function ParseStatus() {
  const status = useParseStore((state) => state.status);
  const percent = useParseStore((state) => state.percent);
  const message = useParseStore((state) => state.message);
  const result = useParseStore((state) => state.result);
  const errorMessage = useParseStore((state) => state.errorMessage);

  if (status === "idle") {
    return null;
  }

  if (status === "parsing") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">解析狀態</h2>
        <p className="parse-main">解析中... {Math.round(percent)}%</p>
        <p className="parse-sub">{message || "處理中"}</p>
      </section>
    );
  }

  if (status === "done") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">解析狀態</h2>
        <p className="parse-main">解析完成</p>
        <p className="parse-sub">
          耗時 {result?.processing_time.toFixed(2) ?? "0.00"} 秒
        </p>
      </section>
    );
  }

  return (
    <section className="parse-status parse-status-error" aria-live="assertive">
      <h2 className="panel-title">解析狀態</h2>
      <p className="parse-main">解析失敗</p>
      <p className="parse-sub">{errorMessage ?? "發生未知錯誤"}</p>
    </section>
  );
}
