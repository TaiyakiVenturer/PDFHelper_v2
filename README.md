# PDFHelper v2

PDFHelper_v2 是 PDFHelper 的重寫版本，目標是把核心流程收斂為可維護、可測試、可擴充的基礎架構。

目前階段先聚焦後端核心能力，優先穩定 MinerU 處理流程與輸出品質，再逐步擴展 API 與前端整合。

## 版本定位

- v1: 舊專題版本，保留既有成果與歷史
- v2: 重寫架構版本，獨立演進

舊版專案連結（v1）：

- https://github.com/TaiyakiVenturer/PDFHelper

## 目前功能

- MinerU CLI 包裝，統一呼叫介面
- FastAPI 應用啟動與生命週期管理
- WebSocket 解析 API（/ws/parse）
- 處理進度回呼與階段化訊息
- 輸出檔案掃描與整理（Markdown/JSON/Images）
- 非法檔名與路徑風險處理
- 基礎自動化測試

## 專案結構

```text
PDFHelper_v2/
├── backend/                 # Python 後端主程式
│   ├── main.py              # FastAPI 啟動入口
│   ├── api/
│   │   └── parse.py         # WebSocket 解析路由
│   ├── models/
│   │   ├── request.py       # API 請求模型
│   │   └── response.py      # API 回應模型
│   ├── services/
│   │   └── mineru.py        # MinerU CLI wrapper
│   ├── tests/               # 後端測試
│   └── pyproject.toml       # 後端相依與設定
├── data/
│   ├── pdfs/                # 待處理 PDF
│   └── mineru_outputs/      # 解析輸出
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

- WebSocket: `/ws/parse`
- 送出 JSON 請求欄位：
- `pdf_path`（必要）
- `method`（`auto` / `txt` / `ocr`）
- `lang`（預設 `en`）
- `formula`（預設 `true`）
- `table`（預設 `true`）

流程上會先推送進度訊息，完成後回傳結果訊息（含 `markdown_path`、`json_path`、`image_path`）。

## 輸出內容

預設輸出位置在 data/mineru_outputs/，每份文件通常包含：

- *.md: 轉換後 Markdown
- *_content_list.json 或 *_content_list_v2.json: 結構化內容
- images/: 擷取圖片

## 測試

```bash
cd backend
uv run pytest -q
```

## Roadmap

- [x] 建立 MinerU CLI wrapper 與基礎測試
- [x] 整理 v2 專案骨架與資料路徑
- [x] 建立第一版 WebSocket parse API
- [ ] 補齊 REST API 與錯誤碼規範
- [ ] 導入批次處理與任務佇列
- [ ] 完成 frontend 與 backend 事件流整合
- [ ] 增加部署與疑難排解文件

## 已知限制

- 目前僅提供 WebSocket parse API，尚未提供 REST API
- frontend 尚未與 v2 後端完成對接
- README 會隨功能落地持續更新
