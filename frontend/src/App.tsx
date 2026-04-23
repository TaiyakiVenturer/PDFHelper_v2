import { FileManager } from "./components/FileManager";
import { ParseStatus } from "./components/ParseStatus";
import { Toast } from "./components/Toast";
import { TranslateStatus } from "./components/TranslateStatus";
import "./app.css";

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title-wrap">
          <h1 className="app-title">PDFHelper Frontend</h1>
          <p className="app-subtitle">原檔管理、Parse 解析與 Translate 翻譯流程</p>
        </div>
        <span className="app-version">v0.1.0</span>
      </header>

      <main className="app-main">
        <div className="main-column">
          <section className="panel">
            <FileManager />
          </section>
          <div className="status-stack">
            <ParseStatus />
            <TranslateStatus />
          </div>
        </div>
      </main>

      <Toast />
    </div>
  );
}

export default App;
