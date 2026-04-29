# PDFHelper v2

PDFHelper_v2 是 PDFHelper 的重寫版本，目標是把核心流程收斂為可維護、可測試、可擴充的基礎架構。

目前採「FastAPI 後端 + Tauri/React 前端」雙軌開發：
後端已完成 parse/translate/index/query 主流程與 artifact/chroma 生命週期管理；
前端已完成檔案管理、parse/translate/index WebSocket 流程與 query 串流 UI。

## 狀態更新（2026-04-29）

- **後端暖機與載入記錄**：啟動時背景預熱重型套件（torch/sentence-transformers/llama-cpp/huggingface-hub），加入載入耗時日志
- **bge-m3 / LLM 載入流程整理**：嵌入與 LLM 依賴改為延遲 import，bge-m3 固定使用 CPU，卸載流程更安全
- **Query prompt 來源格式與數學格式規則**：來源標題改為 Page/Section 結構，新增 inline/block 公式格式指引
- **索引內容與前端跳轉體驗**：行內公式 chunk 改為 $$ 區塊；Query 來源新增「跳至段落」按鈕，可自動捲動並高亮對應段落
- **Query 檢索內容顯示調整**：來源文字使用 Markdown + KaTeX 渲染，回答輸出修正星號空白，側欄寬度與 hover/visibility 動效微調

## 狀態更新（2026-04-28）

- **前後端資料交換統一化**：前端完全不接觸後端內部路徑，所有操作改以 `collection_name` 為唯一識別子
  - `ParseRequest` 改為 `collection_name`（後端自行查找對應 PDF）
  - `TranslateRequest` / `IndexRequest` 改為 `collection_name + method`（後端自行構建 artifact 路徑）
  - `ParseResultMessage` 回傳 `collection_name`，移除 `markdown_path` / `json_path` / `image_dir`
  - `TranslateResultMessage` 移除 `translated_markdown_path`
  - `IndexResultMessage` 移除 `collection_name`（前端已持有）
  - `FileStatusResponse` 改為三個獨立布林值：`is_parsed` / `is_translated` / `is_indexed`，另附 `parse_method` 讓下游操作自動帶入正確 method，移除原 `stage` 字串與各 path 欄位
  - `FileItem` 改為 `pdf_name + collection_name`，移除 `path`
  - `GET /file/{collection_name}/status` 移除 `?method=` 查詢參數（後端自動偵測）
  - `resolve_collection_name` 內化為 `PipelineOrchestrator._resolve_collection_name`，僅在生成 collection_name 的入口（`list_files` / `upload_file` / `_find_pdf_by_collection_name`）呼叫，其餘 pipeline 一律信任傳入值
- `useTranslateStore` 的 `confirmOverwrite` 邏輯提取為獨立函式 `startWebSocketTranslate`，消除重複的 WS 連線程式碼
- **新增 Markdown 取用 API 與靜態資源代理**
  - `GET /file/{collection_name}/markdown?version=original|translated` 回傳 Markdown 文字內容
  - 新增 `/static/artifacts` 靜態路由，Markdown 內圖片連結自動轉為可直接存取的 URL
- **檔案清單回應補上上傳時間**：`FileItem` / `list_files` / `upload_file` 增加 `upload_date` 欄位
- **前端資訊架構與閱覽體驗更新**
  - 新增三分頁導覽：上傳、管理、查詢/閱覽
  - 查詢頁整合「雙欄原文/翻譯 Markdown 閱覽」與側邊問答查詢面板
  - 新增索引狀態檢查列與覆寫確認對話框（解析/索引）

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
│   ├── api/
│   │   ├── deps.py          # WebSocket 共用依賴與流程
│   │   ├── http.py          # REST 路由
│   │   ├── query.py         # Query WebSocket 路由
│   │   └── ws.py            # WebSocket 路由
│   ├── schemas/
│   │   ├── request.py       # API 請求模型
│   │   └── response.py      # API 回應模型
│   ├── services/
│   │   ├── orchestrator.py  # pipeline 編排
│   │   ├── indexer/         # index 相關服務（chunk/embed/chroma）
│   │   ├── llm/             # llama factory 與 query prompt 組裝
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
- [ ] 增加部署與疑難排解文件

## 已知限制

- `WS /ws/query` 目前每次查詢都會載入/卸載 LLM，連續提問時延遲較高
- 首次載入 bge-m3 可能需要下載模型（約 2.3 GB），索引啟動時間會較長
- `WS /ws/query` 目前每次查詢都會載入/卸載 LLM，連續提問時延遲較高（已知，待優化）
- README 會隨功能落地持續更新
