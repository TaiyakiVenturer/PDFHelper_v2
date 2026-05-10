# PDFHelper v2

PDFHelper_v2 是 PDFHelper 的重寫版本，目標是把核心流程收斂為可維護、可測試、可擴充的基礎架構。

目前採「FastAPI 後端 + Tauri/React 前端」雙軌開發：
後端已完成 parse/translate/index/query 主流程與 artifact/chroma 生命週期管理；
前端已完成檔案管理、parse/translate/index WebSocket 流程與 query 串流 UI。

## 狀態更新（2026-05-10）

- **資料路徑改為系統目錄**：應用程式資料從專案相對路徑改為 `%LOCALAPPDATA%\PDFHelper\`，支援環境變數 `PDFHELPER_DATA_DIR` 覆寫（開發用）
- **新增 `backend/core/` 模組**：`paths.py`（路徑解析）與 `config.py`（設定服務）從 `services/` 獨立出來，集中管理 app 層級基礎設施
- **LLM 後端重構**：新增 `services/llm/base.py`（LLMClientProtocol + 工廠函式）與 `openai_compat_factory.py`（OpenAI 相容 API 適配器），支援 Ollama / OpenAI / Groq / 自訂 endpoint
- **翻譯提示詞獨立模組**：`translator_prompts.py` 提取翻譯系統提示、決策規則與 few-shot 範例
- **移除分散的 config 模組**：`indexer_config.py` 與 `translator_config.py` 刪除，常數就地內化
- **前端設定頁面**：新增 `SettingsPage`，支援 LLM 後端切換（llama.cpp / Ollama / OpenAI / Groq / 自訂）、模型選擇、遠端連線探測
- **依賴更新**：`mineru[pipeline]` 鎖定至 `3.1.10`，移除 torch CUDA 11.8 自訂 index（改由 mineru 依賴鏈處理），新增 `openai>=1.0.0`
- **預設 `n_gpu_layers` 改為 `-1`**（全部 GPU 層），原 `0`（CPU 推理）實際不可用

## 狀態更新（2026-04-29）

- **後端暖機與載入記錄**：啟動時背景預熱重型套件（torch/sentence-transformers/llama-cpp/huggingface-hub），加入載入耗時日志
- **bge-m3 / LLM 載入流程整理**：嵌入與 LLM 依賴改為延遲 import，bge-m3 固定使用 CPU，卸載流程更安全
- **Query prompt 來源格式與數學格式規則**：來源標題改為 Page/Section 結構，新增 inline/block 公式格式指引
- **索引內容與前端跳轉體驗**：行內公式 chunk 改為 $$ 區塊；Query 來源新增「跳至段落」按鈕，可自動捲動並高亮對應段落
- **Query 檢索內容顯示調整**：來源文字使用 Markdown + KaTeX 渲染，回答輸出修正星號空白，側欄寬度與 hover/visibility 動效微調）

## 版本定位

- v1: 舊專題版本，保留既有成果與歷史
- v2: 重寫架構版本，獨立演進

舊版專案連結（v1）：

- https://github.com/TaiyakiVenturer/PDFHelper

## 目前功能

- MinerU CLI 包裝，統一呼叫介面
- FastAPI 應用啟動與生命週期管理
- WebSocket API（`/ws/parse`、`/ws/translate`、`/ws/index`、`/ws/query`）
- HTTP API（`/files`、`/file/upload`、`/file/{filename}`、`/artifact/{collection_name}`）
- 處理進度回呼與階段化訊息
- 輸出檔案掃描與整理（JSON/Images）
- 結構感知索引流程（paragraph/equation/table/chart/image/algorithm）
- ChromaDB collection 建立、覆寫與刪除
- Markdown 重建服務骨架（`backend/services/reconstructor/md_reconstructor.py`）
- 前端桌面介面（Tauri）已串接：檔案列表、上傳、刪除、parse/translate/index 進度顯示與 query 串流 UI
- 非法檔名與路徑風險處理

## 專案結構

```text
PDFHelper_v2/
├── backend/                 # Python 後端主程式
│   ├── main.py              # FastAPI 啟動入口
│   ├── core/
│   │   ├── paths.py         # 路徑解析（%LOCALAPPDATA%\PDFHelper）
│   │   └── config.py        # 應用設定服務（config.json 讀寫）
│   ├── api/
│   │   ├── deps.py          # WebSocket 共用依賴與流程
│   │   ├── http.py          # REST 路由
│   │   ├── query.py         # Query WebSocket 路由
│   │   └── ws.py            # WebSocket 路由
│   ├── schemas/
│   │   ├── config.py        # AppConfig / LLMConfig Pydantic 模型
│   │   ├── request.py       # API 請求模型
│   │   └── response.py      # API 回應模型
│   ├── services/
│   │   ├── orchestrator.py  # pipeline 編排
│   │   ├── indexer/         # index 相關服務（chunk/embed/chroma）
│   │   ├── llm/             # LLM 工廠（llama.cpp / OpenAI 相容）
│   │   ├── parser/          # parse 相關服務
│   │   ├── reconstructor/   # markdown 重建相關服務
│   │   └── translator/      # translate 相關服務（模型/提示詞）
│   └── pyproject.toml       # 後端相依與設定
├── docs/                    # 規格與文件
└── frontend/                # Tauri + React 前端
    └── src/
        ├── pages/           # 頁面元件（含 SettingsPage）
        ├── components/      # 共用元件
        ├── stores/          # Zustand 狀態管理
        ├── services/        # API 呼叫層
        └── types/           # TypeScript 型別
```

> 應用程式資料（PDF、artifacts、向量索引、設定）存放於 `%LOCALAPPDATA%\PDFHelper\`，不再依賴專案目錄結構。

## 環境需求

- Python 3.12+
- uv
- Node.js 20+
- pnpm
- Rust toolchain（Tauri 開發/打包需要）

## 快速開始

1. 啟動後端（Terminal A）

```bash
cd backend
uv sync
uv run main.py
```

後端預設監聽：`http://127.0.0.1:8080`

2. 啟動前端（Terminal B）

```bash
cd frontend
pnpm install
pnpm tauri dev
```

3. 在前端操作

- 可直接拖曳上傳 PDF
- 可從檔案列表觸發 parse，並即時查看 WebSocket 進度

4. （可選）前端環境變數

預設會連到本機後端；若要改位址，可在前端設定：

```bash
VITE_BACKEND_HTTP_ORIGIN=http://127.0.0.1:8080
VITE_BACKEND_WS_ORIGIN=ws://127.0.0.1:8080
```

## API（目前）

所有操作以 `collection_name` 為文件識別子（= 後端對 PDF stem 做 sanitization 後的結果）。
上傳與刪除原始檔案以 `source_path` / `filename` 操作，其餘端點均使用 `collection_name`。

- WebSocket（所有 stage 先推送 `progress`，再回傳 `result` 或 `error`）
  - `WS /ws/parse`
    - request: `collection_name`, `method`, `lang`, `formula`, `table`
    - result: `collection_name`, `processing_time`
  - `WS /ws/translate`
    - request: `collection_name`, `method`, `src_lang`, `tgt_lang`
    - result: `translated_count`, `skipped_count`, `processing_time`
  - `WS /ws/index`
    - request: `collection_name`, `method`
    - result: `chunk_count`, `processing_time`
  - `WS /ws/query`
    - request: `question`, `collection_name`, `top_k`(optional), `history`(optional)
    - response stream: `sources` → `delta`(multiple) → `done`（或 `error`）

- HTTP
  - `GET /files`: 讀取 `data/pdfs/` 檔案列表，回傳 `[{pdf_name, collection_name}]`
  - `POST /file/upload`: 上傳（複製）外部 PDF 到 `data/pdfs/`
    - request: `source_path`
    - response: `{pdf_name, collection_name}`
  - `DELETE /file/{filename}`: 刪除 `data/pdfs/` 原始 PDF（以原始檔名操作）
  - `GET /file/{collection_name}/status`: 查詢文件目前狀態
    - response: `{is_parsed, parse_method, is_translated, is_indexed}`
  - `DELETE /artifact/{collection_name}`: 刪除 artifacts 與對應 Chroma collection

## 輸出內容

預設輸出位置在 data/artifacts/{stem}/{method}/，每份文件通常包含：

- *_content_list_merged.json: parse 階段合併後內容
- *_translated.json: translate 階段輸出
- *_translate_progress.json: 翻譯中繼進度（斷點續傳用，完成後自動刪除）
- images/: 擷取圖片
- *.md/\*_translated.md: 重組後的 Markdown 輸出

## Roadmap

- [x] 建立 MinerU CLI wrapper 與基礎測試
- [x] 整理 v2 專案骨架與資料路徑
- [x] 建立 WebSocket parse/translate/index 路由骨架
- [x] 補上 REST API 端點（status/delete/query）
- [x] 完成 Index pipeline（chunking + ChromaDB）
- [x] 完成 Query pipeline（檢索 + 生成）
- [x] 完成 Markdown 重建流程（origin/translated）
- [x] 完成 frontend parse/translate 與 backend 事件流整合
- [x] 完成 frontend index/query UI
- [x] 統一前後端資料交換：前端以 collection_name 為唯一識別子，移除所有路徑暴露
- [x] 資料路徑改為 `%LOCALAPPDATA%`，建立 `core/` 基礎設施模組
- [x] LLM 後端支援 llama.cpp / OpenAI 相容（Ollama / OpenAI / Groq / 自訂）
- [x] 前端設定頁面：LLM 後端切換與模型參數調整
- [ ] 打包安裝檔（Inno Setup）
- [ ] 增加部署與疑難排解文件

## 已知限制

- 首次載入 bge-m3 可能需要下載模型（約 2.3 GB），索引啟動時間會較長
- 首次使用 `query` 功能需要下載模型.gguf，下載完畢後續使用只需載入模型
- `WS /ws/query` 目前每次查詢都會載入/卸載 LLM，連續提問時延遲較高（已知，待優化）
- README 會隨功能落地持續更新
