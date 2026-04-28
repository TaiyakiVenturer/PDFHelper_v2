from typing import Any

from fastapi import APIRouter, WebSocket

from api.deps import REQUEST_PAYLOAD_TIMEOUT_SEC
from api.deps import get_orchestrator
from api.deps import run_ws_stage
from schemas.request import IndexRequest
from schemas.request import ParseRequest
from schemas.request import TranslateRequest
from schemas.response import IndexResultMessage
from schemas.response import ParseResultMessage
from schemas.response import TranslateResultMessage

router = APIRouter()


def _parse_orchestrator_kwargs(request: ParseRequest) -> dict[str, Any]:
    return {
        "collection_name": request.collection_name,
        "method": request.method,
        "lang": request.lang,
        "formula": request.formula,
        "table": request.table,
    }


def _translate_orchestrator_kwargs(request: TranslateRequest) -> dict[str, Any]:
    return {
        "collection_name": request.collection_name,
        "method": request.method,
        "src_lang": request.src_lang,
        "tgt_lang": request.tgt_lang,
    }


def _index_orchestrator_kwargs(request: IndexRequest) -> dict[str, Any]:
    return {
        "collection_name": request.collection_name,
        "method": request.method,
    }


@router.websocket("/ws/parse")
async def ws_parse(websocket: WebSocket) -> None:
    orchestrator = get_orchestrator()
    await run_ws_stage(
        websocket=websocket,
        stage="parse",
        request_type=ParseRequest,
        result_type=ParseResultMessage,
        orchestrator_fn=orchestrator.run_parse,
        orchestrator_kwargs_fn=_parse_orchestrator_kwargs,
        request_timeout_sec=REQUEST_PAYLOAD_TIMEOUT_SEC,
    )


@router.websocket("/ws/translate")
async def ws_translate(websocket: WebSocket) -> None:
    orchestrator = get_orchestrator()
    await run_ws_stage(
        websocket=websocket,
        stage="translate",
        request_type=TranslateRequest,
        result_type=TranslateResultMessage,
        orchestrator_fn=orchestrator.run_translate,
        orchestrator_kwargs_fn=_translate_orchestrator_kwargs,
        request_timeout_sec=REQUEST_PAYLOAD_TIMEOUT_SEC,
    )


@router.websocket("/ws/index")
async def ws_index(websocket: WebSocket) -> None:
    orchestrator = get_orchestrator()
    await run_ws_stage(
        websocket=websocket,
        stage="index",
        request_type=IndexRequest,
        result_type=IndexResultMessage,
        orchestrator_fn=orchestrator.run_index,
        orchestrator_kwargs_fn=_index_orchestrator_kwargs,
        request_timeout_sec=REQUEST_PAYLOAD_TIMEOUT_SEC,
    )
