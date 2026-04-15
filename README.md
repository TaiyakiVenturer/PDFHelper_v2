# PDFHelper v2

PDFHelper_v2 是 PDFHelper 的重寫版本，目標是把核心流程收斂為可維護、可測試、可擴充的基礎架構。

目前階段先聚焦後端核心能力，優先穩定 MinerU 處理流程與輸出品質，再逐步擴展 API 與前端整合。

## 狀態更新（2026-04-15）

- API 路由已拆分為 WebSocket 與 HTTP（`backend/api/ws.py`、`backend/api/http.py`）
- 請求/回應模型已移至 `backend/schemas/`
- 流程編排統一由 `PipelineOrchestrator` 管理（parse/translate/index/query/status/delete）
- translator 服務已拆分模型邏輯與設定（`model_translator.py`、`translator_config.py`）
- markdown reconstructor 服務骨架已建立（`backend/services/reconstructor/md_reconstructor.py`）
- parse 與 translate 可用；index 與 query 仍為骨架實作

## 版本定位

- v1: 舊專題版本，保留既有成果與歷史
- v2: 重寫架構版本，獨立演進

舊版專案連結（v1）：

- https://github.com/TaiyakiVenturer/PDFHelper

## 目前功能

- MinerU CLI 包裝，統一呼叫介面
- FastAPI 應用啟動與生命週期管理
- WebSocket API（`/ws/parse`、`/ws/translate`、`/ws/index`）
- HTTP API（`/file/{collection_name}/status`、`/file/{collection_name}`、`/query`）
- 處理進度回呼與階段化訊息
- 輸出檔案掃描與整理（JSON/Images）
- Markdown 重建服務骨架（`backend/services/reconstructor/md_reconstructor.py`）
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
│   │   ├── parser/          # parse 相關服務
│   │   ├── reconstructor/   # markdown 重建相關服務
│   │   └── translator/      # translate 相關服務（模型/設定）
│   └── pyproject.toml       # 後端相依與設定
├── data/
│   ├── pdfs/                # 待處理 PDF
│   └── artifacts/           # 統一流程產物（parse/translate 等）
├── docs/                    # 規格與文件
└── frontend/                # 前端（待整合）
```

## 環境需求

- Python 3.12+
- uv
- MinerU 可用執行環境

## 快速開始

1. 安裝依賴

```bash
cd backend
uv sync
```

2. 準備 PDF

- 將檔案放到 data/pdfs/

3. 執行

```bash
cd backend
uv run main.py
```

啟動後預設監聽：`http://127.0.0.1:8080`

## API（目前）

- WebSocket
- `/ws/parse`
- request: `pdf_path`, `method`, `lang`, `formula`, `table`
- `/ws/translate`
- request: `json_path`, `src_lang`, `tgt_lang`
- `/ws/index`
- request: `json_path`

所有 WebSocket stage 都會先推送 `progress` 訊息，再回傳 `result` 或 `error` 訊息。

- HTTP
- `GET /file/{collection_name}/status`: 查詢文件目前階段（none/parsed/translated/indexed）
- `DELETE /file/{collection_name}`: 刪除對應文件與產物
- `POST /query`: 目前已提供端點骨架，回傳格式固定為 `answer + sources`

## 輸出內容

預設輸出位置在 data/artifacts/{stem}/{method}/，每份文件通常包含：

- *_content_list_merged.json: parse 階段合併後內容
- *_translated.json: translate 階段輸出
- images/: 擷取圖片

## 測試

```bash
cd backend
uv run pytest -q
```

## Roadmap

- [x] 建立 MinerU CLI wrapper 與基礎測試
- [x] 整理 v2 專案骨架與資料路徑
- [x] 建立 WebSocket parse/translate/index 路由骨架
- [x] 補上 REST API 端點（status/delete/query）
- [ ] 完成 Index pipeline（chunking + ChromaDB）
- [ ] 完成 Query pipeline（檢索 + 生成）
- [ ] 完成 Markdown 重建流程（origin/translated）
- [ ] 導入批次處理與任務佇列
- [ ] 完成 frontend 與 backend 事件流整合
- [ ] 增加部署與疑難排解文件

## 已知限制

- `/ws/index` 目前回傳 not implemented（流程尚未落地）
- `POST /query` 目前為骨架回傳，尚未接入檢索與 LLM
- parse/translate 階段尚未產生 markdown 重建輸出
- frontend 尚未與 v2 後端完成對接
- README 會隨功能落地持續更新
