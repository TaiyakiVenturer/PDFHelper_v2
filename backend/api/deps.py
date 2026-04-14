import asyncio
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from typing import TypeVar

from fastapi import WebSocket
from pydantic import BaseModel
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from services.orchestrator import PipelineOrchestrator
from services.error_utils import build_error_message
from schemas.response import ProgressMessage

REQUEST_PAYLOAD_TIMEOUT_SEC = 10.0

_DATA_DIR = str((Path(__file__).resolve().parents[2] / "data").resolve())
_ORCHESTRATOR = PipelineOrchestrator(data_dir=_DATA_DIR)
RequestT = TypeVar("RequestT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)


def get_orchestrator() -> PipelineOrchestrator:
    return _ORCHESTRATOR


async def send_progress_messages(
    websocket: WebSocket,
    queue: asyncio.Queue[tuple[float, str]],
    finished: asyncio.Event,
) -> None:
    while True:
        if finished.is_set() and queue.empty():
            break

        try:
            percent, message = await asyncio.wait_for(queue.get(), timeout=0.2)
        except TimeoutError:
            continue

        payload = ProgressMessage(percent=percent, message=message)
        try:
            await websocket.send_text(payload.model_dump_json())
        except (WebSocketDisconnect, RuntimeError):
            return


async def run_ws_stage(
    websocket: WebSocket,
    stage: str,
    request_type: type[RequestT],
    result_type: type[ResultT],
    orchestrator_fn: Callable[..., ResultT],
    orchestrator_kwargs_fn: Callable[[RequestT], dict[str, Any]],
    request_timeout_sec: float = REQUEST_PAYLOAD_TIMEOUT_SEC,
) -> None:
    await websocket.accept()

    try:
        raw_request = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=request_timeout_sec,
        )
    except WebSocketDisconnect:
        return
    except TimeoutError:
        payload = build_error_message(
            stage=stage,
            code=f"REQ_{stage.upper()}_PAYLOAD_TIMEOUT",
            category="request",
            message=(
                "No request payload received within "
                f"{request_timeout_sec:.0f}s"
            ),
            retryable=True,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_text(payload.model_dump_json())
            await websocket.close()
        return
    except Exception as error:
        payload = build_error_message(
            stage=stage,
            code=f"REQ_{stage.upper()}_RECEIVE_FAILED",
            category="request",
            message="Failed to receive request payload",
            detail=str(error),
            retryable=True,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_text(payload.model_dump_json())
            await websocket.close()
        return

    try:
        request = request_type.model_validate_json(raw_request)
    except ValidationError as error:
        payload = build_error_message(
            stage=stage,
            code=f"REQ_{stage.upper()}_INVALID_PAYLOAD",
            category="request",
            message="Invalid request payload",
            detail=str(error),
            retryable=False,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_text(payload.model_dump_json())
            await websocket.close()
        return

    progress_queue: asyncio.Queue[tuple[float, str]] = asyncio.Queue()
    finished = asyncio.Event()
    loop = asyncio.get_running_loop()

    def on_progress(percent: float, message: str) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, (percent, message))

    sender_task = asyncio.create_task(
        send_progress_messages(websocket, progress_queue, finished)
    )

    try:
        result = await asyncio.to_thread(
            orchestrator_fn,
            **orchestrator_kwargs_fn(request),
            on_progress=on_progress,
        )
    finally:
        finished.set()
        with suppress(WebSocketDisconnect, RuntimeError):
            await sender_task

    if not result.success:
        payload = build_error_message(
            stage=stage,
            code=result.error_code,
            category=result.error_category,
            message=result.error,
            retryable=result.retryable,
        )
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_text(payload.model_dump_json())
            await websocket.close()
        return

    with suppress(WebSocketDisconnect, RuntimeError):
        await websocket.send_text(result_type.model_validate(result).model_dump_json())
        await websocket.close()
