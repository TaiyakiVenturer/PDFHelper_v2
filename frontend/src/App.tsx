import { Navigate, Route, Routes } from "react-router-dom";
import { AppNav } from "./components/AppNav";
import { Toast } from "./components/Toast";
import { FilesPage } from "./pages/FilesPage";
import { HomePage } from "./pages/HomePage";
import { QueryPage } from "./pages/QueryPage";
import "./app.css";

function App() {
  return (
    <div className="app-shell">
      <AppNav />

      <main className="app-main">
        <Routes>
          <Route path="/home" element={<HomePage />} />
          <Route path="/files" element={<FilesPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </main>

      <Toast />
    </div>
  );
}

export default App;
