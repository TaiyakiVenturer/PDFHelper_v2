# PDFHelper v2

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/TaiyakiVenturer/PDFHelper_v2)

以 FastAPI 後端 + Tauri/React 前端為基礎的 PDF 學術論文助理，支援解析、翻譯、語意索引與 RAG 查詢。

舊版（v1）：https://github.com/TaiyakiVenturer/PDFHelper

## 功能

- PDF 結構解析（MinerU）：paragraph / equation / table / chart / image / algorithm
- 論文翻譯（逐段翻譯，支援斷點續傳）
- 語意索引與 RAG 查詢（ChromaDB + bge-m3 + LLM）
- LLM 後端可切換：llama.cpp（本地 .gguf）/ Ollama / OpenAI / Groq / 自訂 endpoint
- Markdown 重建與圖片瀏覽
- LLM query 改寫（查詢前將問題改寫為關鍵詞搜尋 query）

## 安裝（一般使用者）

執行 `PDFHelper-Setup-1.0.0.exe`，安裝精靈會自動完成所有步驟：

1. 安裝程式本體至 `%LOCALAPPDATA%\PDFHelper\`
2. 偵測 NVIDIA 顯示卡（`nvcuda.dll`）
   - 有 NVIDIA GPU：安裝 CUDA 12.6 加速版依賴（約 5.5 GB）
   - 無 GPU：安裝 CPU 版依賴（約 3 GB）
3. 在背景執行 `uv sync` 下載 Python 套件（需網路，約 10–20 分鐘）

安裝完成後直接從開始功能表或桌面捷徑啟動，無需手動開啟後端。

> **需求**：Windows 10 1809+ / x64；NVIDIA GPU 使用者建議先安裝最新顯示卡驅動

## 內建模型

首次使用時會自動從 HuggingFace 下載，無需手動操作。

| 用途 | 模型 | 下載大小 | 資源消耗 |
|---|---|---|---|
| 語意嵌入（索引 / 檢索）| [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) | 約 2.3 GB | CPU，RAM 約 4 GB |
| 問答生成（llama.cpp 預設）| [Qwen2.5-7B-Instruct-Q4_K_M](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF) | 約 4.7 GB | VRAM 約 5–6 GB |

- bge-m3 固定使用 CPU，不佔 VRAM
- Qwen2.5-7B Q4_K_M 在 `n_gpu_layers=-1`（預設）、`n_ctx=4096` 下約需 5–6 GB VRAM，最低配置建議 6 GB 顯示卡（如 GTX 1660 Super / RTX 2060）
- 使用 Ollama / OpenAI / Groq 等外部後端時不需下載 .gguf，VRAM 需求由外部服務決定

## 開發環境

**環境需求**：Python 3.12、uv、Node.js 20+、pnpm、Rust toolchain

```bash
# Terminal A：後端
cd backend
uv sync
uv run main.py          # 監聽 http://127.0.0.1:12230

# Terminal B：前端
cd frontend
pnpm install
pnpm tauri dev
```

環境變數（可選）：

```bash
VITE_BACKEND_HTTP_ORIGIN=http://127.0.0.1:12230
VITE_BACKEND_WS_ORIGIN=ws://127.0.0.1:12230
```

## API

後端預設監聽 `http://127.0.0.1:12230`。

**WebSocket**（進度推送 → result / error）

| 端點 | 主要欄位 |
|---|---|
| `WS /ws/parse` | `collection_name`, `method`, `lang`, `formula`, `table` |
| `WS /ws/translate` | `collection_name`, `method`, `src_lang`, `tgt_lang` |
| `WS /ws/index` | `collection_name`, `method` |
| `WS /ws/query` | `question`, `collection_name`, `top_k`, `history` → stream |

**HTTP — 檔案**

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/files` | 列出所有 PDF |
| POST | `/file/upload` | 上傳 PDF（`source_path`） |
| DELETE | `/file/{filename}` | 刪除原始 PDF |
| GET | `/file/{name}/status` | 查詢解析/翻譯/索引狀態 |
| GET | `/file/{name}/markdown` | 取得 Markdown（`?version=original\|translated`） |
| DELETE | `/artifact/{name}` | 刪除 artifacts + Chroma collection |

**HTTP — 設定**

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET/PUT | `/settings` | 讀寫 AppConfig |
| GET | `/settings/models/local` | 列出本地 .gguf 檔案 |
| POST | `/settings/probe` | 探測 OpenAI 相容端點 |

**靜態資源**：`GET /static/artifacts/{name}/{method}/...`（Markdown 圖片）

## 資料位置

| 類型 | 路徑 |
|---|---|
| 應用程式資料 | `%LOCALAPPDATA%\PDFHelper\` |
| PDF 原始檔 | `%LOCALAPPDATA%\PDFHelper\pdfs\` |
| Artifacts | `%LOCALAPPDATA%\PDFHelper\artifacts\{name}\{method}\` |
| 本地模型（.gguf）| `%LOCALAPPDATA%\PDFHelper\models\` |
| 設定檔 | `%LOCALAPPDATA%\PDFHelper\config.json` |

Artifacts 內容：`*_content_list_merged.json`、`*_translated.json`、`images/`、`*.md`

## 專案結構

```
PDFHelper_v2/
├── backend/
│   ├── main.py              # FastAPI 入口（port 12230）
│   ├── core/                # paths / config / prewarm / watcher
│   ├── api/                 # http / ws / query 路由
│   ├── schemas/             # Pydantic 模型
│   └── services/            # orchestrator / parser / translator / indexer / llm / reconstructor
└── frontend/
    ├── src-tauri/src/lib.rs # Tauri 主程式（release 自動啟動後端）
    └── src/                 # pages / components / stores / services / types
```

## Roadmap

- [x] Parse / Translate / Index / Query 完整 pipeline
- [x] ChromaDB 語意索引（bge-m3）
- [x] LLM 多後端支援（llama.cpp / OpenAI 相容）
- [x] 前端全功能 UI（檔案管理、進度顯示、query 串流、設定頁面）
- [x] 資料路徑統一至 `%LOCALAPPDATA%`
- [x] Tauri release 自動啟動/終止後端
- [x] LLM query 改寫
- [x] Markdown API + 靜態圖片服務
- [x] Inno Setup 安裝程式（CUDA / CPU 自動偵測）
- [ ] 部署與疑難排解文件

## 已知限制

- 首次使用索引需下載 bge-m3（約 2.3 GB）
- 首次查詢需下載 .gguf 模型（使用 llama.cpp 後端時）
- 每次 query 會重新載入 LLM（連續提問延遲較高，待優化）
