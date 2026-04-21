# PDFHelper v2

PDFHelper_v2 是 PDFHelper 的重寫版本，目標是把核心流程收斂為可維護、可測試、可擴充的基礎架構。

目前採「FastAPI 後端 + Tauri/React 前端」雙軌開發：
後端已完成 parse/translate/index 主流程與 artifact/chroma 生命週期管理；
前端已完成檔案管理與 parse WebSocket 解析流程，translate/index/query UI 仍持續補齊。

## 狀態更新（2026-04-22）

- API 路由已拆分為 WebSocket 與 HTTP（`backend/api/ws.py`、`backend/api/http.py`）
- 請求/回應模型已移至 `backend/schemas/`
- 流程編排統一由 `PipelineOrchestrator` 管理（parse/translate/index/query/status/delete）
- translator 服務已拆分模型邏輯與設定（`model_translator.py`、`translator_config.py`）
- markdown reconstructor 服務骨架已建立（`backend/services/reconstructor/md_reconstructor.py`）
- index pipeline 已落地（chunker + bge-m3 embedding + ChromaDB 寫入）
- stage-level 互斥已套用於 parse/translate/index，避免重量級流程並行造成資源衝突
- `delete_artifacts` 會連動刪除對應 ChromaDB collection
- query 仍為骨架回應（`answer + sources`）

## 版本定位

- v1: 舊專題版本，保留既有成果與歷史
- v2: 重寫架構版本，獨立演進

舊版專案連結（v1）：

- https://github.com/TaiyakiVenturer/PDFHelper

## 目前功能

- MinerU CLI 包裝，統一呼叫介面
- FastAPI 應用啟動與生命週期管理
- WebSocket API（`/ws/parse`、`/ws/translate`、`/ws/index`）
- HTTP API（`/files`、`/file/upload`、`/file/{filename}`、`/artifact/{collection_name}`、`/query`）
- 處理進度回呼與階段化訊息
- 輸出檔案掃描與整理（JSON/Images）
- 結構感知索引流程（paragraph/equation/table/chart/image/algorithm）
- ChromaDB collection 建立、覆寫與刪除
- Markdown 重建服務骨架（`backend/services/reconstructor/md_reconstructor.py`）
- 前端桌面介面（Tauri）已串接：檔案列表、上傳、刪除、parse 進度顯示
- 非法檔名與路徑風險處理
- 基礎自動化測試

## 專案結構

```text
PDFHelper_v2/
├── backend/                 # Python 後端主程式
│   ├── main.py              # FastAPI 啟動入口
│   ├── api/
│   │   ├── deps.py          # WebSocket 共用依賴與流程
│   │   ├── http.py          # REST 路由
│   │   └── ws.py            # WebSocket 路由
│   ├── schemas/
│   │   ├── request.py       # API 請求模型
│   │   └── response.py      # API 回應模型
│   ├── services/
│   │   ├── orchestrator.py  # pipeline 編排
│   │   ├── indexer/         # index 相關服務（chunk/embed/chroma）
│   │   ├── parser/          # parse 相關服務
│   │   ├── reconstructor/   # markdown 重建相關服務
│   │   └── translator/      # translate 相關服務（模型/設定）
│   └── pyproject.toml       # 後端相依與設定
├── data/
│   ├── pdfs/                # 待處理 PDF
│   ├── artifacts/           # 統一流程產物（parse/translate 等）
│   └── chroma/              # 本地向量索引資料（per-document collection）
├── docs/                    # 規格與文件
└── frontend/                # Tauri + React 前端
```

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

- WebSocket
- `WS /ws/parse`
	- request: `pdf_path`, `method`, `lang`, `formula`, `table`
- `WS /ws/translate`
	- request: `json_path`, `src_lang`, `tgt_lang`
- `WS /ws/index`
	- request: `json_path`

所有 WebSocket stage 都會先推送 `progress` 訊息，再回傳 `result` 或 `error` 訊息。

- HTTP
- `GET /files`: 讀取 `data/pdfs/` 檔案列表
- `POST /file/upload`: 上傳（複製）外部 PDF 到 `data/pdfs/`
	- request: `source_path`
- `DELETE /file/{filename}`: 刪除 `data/pdfs/` 原始 PDF
- `GET /file/{collection_name}/status?method=auto`: 查詢文件目前階段（none/parsed/translated/indexed）
- `DELETE /artifact/{collection_name}`: 刪除 artifacts 與對應 Chroma collection
- `POST /query`: 目前為骨架回傳，格式為 `answer + sources`
	- request: `question`, `collection_name`, `top_k`

## 輸出內容

預設輸出位置在 data/artifacts/{stem}/{method}/，每份文件通常包含：

- *_content_list_merged.json: parse 階段合併後內容
- *_translated.json: translate 階段輸出
- images/: 擷取圖片
- *.md/\*_translated.md: 重組後的 Markdown 輸出

## Roadmap

- [x] 建立 MinerU CLI wrapper 與基礎測試
- [x] 整理 v2 專案骨架與資料路徑
- [x] 建立 WebSocket parse/translate/index 路由骨架
- [x] 補上 REST API 端點（status/delete/query）
- [x] 完成 Index pipeline（chunking + ChromaDB）
- [ ] 完成 Query pipeline（檢索 + 生成）
- [x] 完成 Markdown 重建流程（origin/translated）
- [ ] 完成 frontend 與 backend 事件流整合
- [ ] 增加部署與疑難排解文件

## 已知限制

- `POST /query` 目前為骨架回傳，尚未接入檢索與 LLM
- 首次載入 bge-m3 可能需要下載模型（約 2.3 GB），索引啟動時間會較長
- 前端目前僅完成檔案管理與 parse 流程；translate/index/query UI 尚未完成
- README 會隨功能落地持續更新
