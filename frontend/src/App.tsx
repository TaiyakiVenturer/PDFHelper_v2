import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppNav } from "./components/AppNav";
import { Toast } from "./components/Toast";
import { FilesPage } from "./pages/FilesPage";
import { HomePage } from "./pages/HomePage";
import { QueryPage } from "./pages/QueryPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./app.css";

const BACKEND_ORIGIN =
  (import.meta.env.VITE_BACKEND_HTTP_ORIGIN as string | undefined)?.trim() ||
  "http://127.0.0.1:12230";

function useBackendReady() {
  const [ready, setReady] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [lastError, setLastError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    const deadline = Date.now() + 60_000;

    const poll = async () => {
      while (!cancelled && Date.now() < deadline) {
        try {
          const res = await fetch(`${BACKEND_ORIGIN}/files`, {
            signal: AbortSignal.timeout(2000),
          });
          if (!cancelled) setLastError(`HTTP ${res.status}`);
          if (res.ok) {
            if (!cancelled) setReady(true);
            return;
          }
        } catch (e) {
          if (!cancelled) setLastError(e instanceof Error ? e.message : String(e));
        }
        await new Promise<void>((r) => setTimeout(r, 800));
      }
      if (!cancelled) setTimedOut(true);
    };

    void poll();
    return () => { cancelled = true; };
  }, []);

  return { ready, timedOut, lastError };
}

function App() {
  const { ready, timedOut, lastError } = useBackendReady();

  if (timedOut) {
    return (
      <div className="backend-startup">
        <div className="backend-startup-card">
          <div className="backend-startup-icon">⚠️</div>
          <h1 className="backend-startup-title">PDFHelper</h1>
          <p className="backend-startup-text">後端啟動逾時，請重新啟動應用程式。</p>
          {lastError && <p className="backend-startup-error">{lastError}</p>}
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="backend-startup">
        <div className="backend-startup-card">
          <div className="backend-startup-icon">📄</div>
          <h1 className="backend-startup-title">PDFHelper</h1>
          <div className="backend-startup-spinner" />
          <p className="backend-startup-text">正在啟動後端服務…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppNav />

      <main className="app-main">
        <Routes>
          <Route path="/home" element={<HomePage />} />
          <Route path="/files" element={<FilesPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </main>

      <Toast />
    </div>
  );
}

export default App;
