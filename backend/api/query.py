from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Generator

from fastapi import APIRouter
from fastapi import WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from api.deps import REQUEST_PAYLOAD_TIMEOUT_SEC
from api.deps import get_orchestrator
from schemas.request import QueryRequest
from services.error_utils import build_error_message

router = APIRouter()


def _next_message(generator: Generator):
    try:
        return next(generator)
    except StopIteration:
        return None


@router.websocket("/ws/query")
async def ws_query(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        raw_request = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=REQUEST_PAYLOAD_TIMEOUT_SEC,
        )
    except WebSocketDisconnect:
        return
    except TimeoutError:
        payload = build_error_message(
            stage="query",
            code="REQ_QUERY_PAYLOAD_TIMEOUT",
            category="request",
            message=(
                "No request payload received within "
                f"{REQUEST_PAYLOAD_TIMEOUT_SEC:.0f}s"
            ),
            retryable=True,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_json(payload.model_dump())
            await websocket.close()
        return
    except Exception as error:
        payload = build_error_message(
            stage="query",
            code="REQ_QUERY_RECEIVE_FAILED",
            category="request",
            message="Failed to receive request payload",
            detail=str(error),
            retryable=True,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_json(payload.model_dump())
            await websocket.close()
        return

    try:
        request = QueryRequest.model_validate_json(raw_request)
    except ValidationError as error:
        payload = build_error_message(
            stage="query",
            code="REQ_QUERY_INVALID_PAYLOAD",
            category="request",
            message="Invalid request payload",
            detail=str(error),
            retryable=False,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_json(payload.model_dump())
            await websocket.close()
        return

    orchestrator = get_orchestrator()
    generator: Generator | None = None

    try:
        generator = orchestrator.run_query(
            question=request.question,
            collection_name=request.collection_name,
            top_k=request.top_k,
            history=request.history,
        )

        while True:
            message = await asyncio.to_thread(_next_message, generator)
            if message is None:
                break

            await websocket.send_json(message.model_dump())
    except WebSocketDisconnect:
        if generator is not None:
            generator.close()
    finally:
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close()
