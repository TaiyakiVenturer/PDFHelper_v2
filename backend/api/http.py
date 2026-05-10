import asyncio
import logging
import re
from typing import Any

from fastapi import APIRouter
from fastapi import Body
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from api.deps import get_orchestrator
from schemas.config import AppConfig
from schemas.request import UploadFileRequest
from schemas.response import DeleteResponse
from schemas.response import FileItem
from schemas.response import FileListResponse
from schemas.response import FileStatusResponse
from core.config import config
from services.llm.base import DEFAULT_MODELS_DIR

logger = logging.getLogger(__name__)

router = APIRouter()


class LocalModelsResponse(BaseModel):
    files: list[str]


class ProbeRequest(BaseModel):
    base_url: str
    api_key: str = "sk-no-key"


class ProbeResponse(BaseModel):
    ok: bool
    models: list[str]
    error: str | None = None


@router.get("/settings", response_model=AppConfig)
async def get_settings() -> AppConfig:
    return config.get_config()


@router.put("/settings", response_model=AppConfig)
async def update_settings(cfg: AppConfig = Body(...)) -> AppConfig:
    config.save_config(cfg)
    return cfg


@router.get("/settings/models/local", response_model=LocalModelsResponse)
async def get_local_models() -> LocalModelsResponse:
    if not DEFAULT_MODELS_DIR.exists():
        return LocalModelsResponse(files=[])
    files = sorted(p.name for p in DEFAULT_MODELS_DIR.glob("*.gguf") if p.is_file())
    return LocalModelsResponse(files=files)


@router.post("/settings/probe", response_model=ProbeResponse)
async def probe_remote(req: ProbeRequest) -> ProbeResponse:
    return await asyncio.to_thread(_do_probe, req.base_url, req.api_key)


def _do_probe(base_url: str, api_key: str) -> ProbeResponse:
    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(base_url=base_url, api_key=api_key)
        models_page = client.models.list()
        model_ids = sorted(m.id for m in models_page.data)
        return ProbeResponse(ok=True, models=model_ids)
    except Exception as exc:
        logger.debug("probe 失敗: %s", exc)
        return ProbeResponse(ok=False, models=[], error=str(exc))


@router.get("/file/{collection_name}/markdown", response_class=PlainTextResponse)
async def get_markdown(
    request: Request,
    collection_name: str,
    version: str = "original",
) -> str:
    orchestrator = get_orchestrator()
    try:
        content, method = await asyncio.to_thread(
            orchestrator.get_markdown_content,
            collection_name,
            version,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    base_url = str(request.base_url).rstrip("/")
    static_prefix = f"{base_url}/static/artifacts/{collection_name}/{method}"
    content = re.sub(
        r"!\[([^\]]*)\]\(images/([^)]+)\)",
        rf"![\1]({static_prefix}/images/\2)",
        content,
    )
    return content


@router.get("/file/{collection_name}/status", response_model=FileStatusResponse)
async def get_file_status(collection_name: str) -> FileStatusResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.get_file_status,
        collection_name,
    )


@router.post("/file/upload", response_model=FileItem)
async def upload_file(request: UploadFileRequest) -> FileItem:
    orchestrator = get_orchestrator()
    try:
        result = await asyncio.to_thread(
            orchestrator.upload_file,
            request.source_path,
        )
    except FileExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return FileItem.model_validate(result)


@router.get("/files", response_model=FileListResponse)
async def get_files() -> FileListResponse:
    orchestrator = get_orchestrator()
    files = await asyncio.to_thread(orchestrator.list_files)
    return FileListResponse(files=[FileItem.model_validate(item) for item in files])


@router.delete("/file/{filename}", response_model=DeleteResponse)
async def delete_file(filename: str) -> DeleteResponse:
    orchestrator = get_orchestrator()
    try:
        return await asyncio.to_thread(
            orchestrator.delete_file,
            filename,
        )
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.delete("/artifact/{collection_name}", response_model=DeleteResponse)
async def delete_artifact(collection_name: str) -> DeleteResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.delete_artifacts,
        collection_name,
    )

