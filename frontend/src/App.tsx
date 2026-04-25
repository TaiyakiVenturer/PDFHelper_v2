import { FileManager } from "./components/FileManager";
import { IndexStatus } from "./components/IndexStatus";
import { ParseStatus } from "./components/ParseStatus";
import { QueryPanel } from "./components/QueryPanel";
import { Toast } from "./components/Toast";
import { TranslateStatus } from "./components/TranslateStatus";
import "./app.css";

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title-wrap">
          <h1 className="app-title">PDFHelper Frontend</h1>
          <p className="app-subtitle">原檔管理、解析、翻譯、索引與查詢流程</p>
        </div>
        <span className="app-version">v0.1.0</span>
      </header>

      <main className="app-main">
        <div className="app-layout">
          <div className="app-left">
            <section className="panel">
              <FileManager />
            </section>
            <div className="status-stack">
              <ParseStatus />
              <TranslateStatus />
              <IndexStatus />
            </div>
          </div>
          <div className="app-right">
            <section className="panel">
              <QueryPanel />
            </section>
          </div>
        </div>
      </main>

      <Toast />
    </div>
  );
}

export default App;
