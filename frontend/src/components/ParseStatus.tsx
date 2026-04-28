import { ProgressBar } from "./ProgressBar";
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

  if (status === "checking") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">解析狀態</h2>
        <p className="parse-main">正在確認檔案狀態...</p>
      </section>
    );
  }

  if (status === "awaitingConfirm") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">解析狀態</h2>
        <p className="parse-main">等待覆寫確認</p>
      </section>
    );
  }

  if (status === "parsing") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">解析狀態</h2>
        <ProgressBar percent={percent} message={message || "處理中"} />
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
