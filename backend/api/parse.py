import asyncio
from contextlib import suppress
from pathlib import Path

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from models.request import ParseRequest
from models.response import ErrorMessage
from models.response import ProgressMessage
from models.response import ResultMessage
from services.mineru import MinerUCLIWrapper

router = APIRouter()
OUTPUT_DIR = str((Path(__file__).resolve().parents[2] / "data" / "mineru_outputs").resolve())
mineru_wrapper = MinerUCLIWrapper(output_dir=OUTPUT_DIR)


async def _send_progress_messages(
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
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return


@router.websocket("/ws/parse")
async def ws_parse(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        raw_request = await websocket.receive_text()
        request = ParseRequest.model_validate_json(raw_request)
    except ValidationError as error:
        payload = ErrorMessage(error=f"Invalid request payload: {error}")
        await websocket.send_text(payload.model_dump_json())
        await websocket.close()
        return
    except Exception as error:
        payload = ErrorMessage(error=f"Failed to receive request: {error}")
        await websocket.send_text(payload.model_dump_json())
        await websocket.close()
        return

    progress_queue: asyncio.Queue[tuple[float, str]] = asyncio.Queue()
    finished = asyncio.Event()
    loop = asyncio.get_running_loop()

    def on_progress(percent: float, message: str) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, (percent, message))

    # KL-02: current spec assumes single-client local usage.
    previous_callback = mineru_wrapper._on_progress
    mineru_wrapper._on_progress = on_progress

    sender_task = asyncio.create_task(
        _send_progress_messages(websocket, progress_queue, finished)
    )

    try:
        result = await asyncio.to_thread(
            mineru_wrapper.process,
            pdf_path=request.pdf_path,
            method=request.method,
            lang=request.lang,
            formula=request.formula,
            table=request.table,
        )
    finally:
        mineru_wrapper._on_progress = previous_callback
        finished.set()
        with suppress(WebSocketDisconnect, RuntimeError):
            await sender_task

    if not result.success:
        payload = ErrorMessage(error=result.error)
        with suppress(WebSocketDisconnect, RuntimeError):
            await websocket.send_text(payload.model_dump_json())
            await websocket.close()
        return

    payload = ResultMessage(
        success=result.success,
        markdown_path=result.output_file_paths.markdown_path,
        json_path=result.output_file_paths.json_path,
        image_path=result.output_file_paths.image_path,
        processing_time=result.processing_time,
        error=result.error,
    )
    with suppress(WebSocketDisconnect, RuntimeError):
        await websocket.send_text(payload.model_dump_json())
        await websocket.close()
