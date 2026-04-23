import { ProgressBar } from "./ProgressBar";
import { useTranslateStore } from "../stores/useTranslateStore";

export function TranslateStatus() {
  const status = useTranslateStore((state) => state.status);
  const percent = useTranslateStore((state) => state.percent);
  const message = useTranslateStore((state) => state.message);
  const result = useTranslateStore((state) => state.result);
  const errorMessage = useTranslateStore((state) => state.errorMessage);
  const targetFilename = useTranslateStore((state) => state.targetFilename);

  if (status === "idle") {
    return null;
  }

  if (status === "checking") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">翻譯狀態</h2>
        <p className="parse-main">正在確認檔案狀態...</p>
      </section>
    );
  }

  if (status === "awaitingConfirm") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">翻譯狀態</h2>
        <p className="parse-main">等待覆寫確認</p>
        <p className="parse-sub">{targetFilename || "目標檔案"}</p>
      </section>
    );
  }

  if (status === "translating") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">翻譯狀態</h2>
        <p className="parse-main">翻譯中... {targetFilename || ""}</p>
        <ProgressBar percent={percent} message={message || "處理中"} />
      </section>
    );
  }

  if (status === "done") {
    return (
      <section className="parse-status" aria-live="polite">
        <h2 className="panel-title">翻譯狀態</h2>
        <p className="parse-main">翻譯完成</p>
        <p className="parse-sub">已翻譯 {result?.translated_count ?? 0} 段</p>
        <p className="parse-sub">已跳過 {result?.skipped_count ?? 0} 段</p>
        <p className="parse-sub">
          耗時 {result?.processing_time.toFixed(2) ?? "0.00"} 秒
        </p>
      </section>
    );
  }

  return (
    <section className="parse-status parse-status-error" aria-live="assertive">
      <h2 className="panel-title">翻譯狀態</h2>
      <p className="parse-main">翻譯失敗</p>
      <p className="parse-sub">{errorMessage ?? "發生未知錯誤"}</p>
    </section>
  );
}
