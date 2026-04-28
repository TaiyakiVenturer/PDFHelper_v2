import asyncio
import re

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.responses import PlainTextResponse

from api.deps import get_orchestrator
from schemas.request import UploadFileRequest
from schemas.response import DeleteResponse
from schemas.response import FileItem
from schemas.response import FileListResponse
from schemas.response import FileStatusResponse

router = APIRouter()


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

