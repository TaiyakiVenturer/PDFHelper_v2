import asyncio

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from api.deps import get_orchestrator
from schemas.request import UploadFileRequest
from schemas.response import DeleteResponse
from schemas.response import FileItem
from schemas.response import FileListResponse
from schemas.response import FileStatusResponse

router = APIRouter()


@router.get("/file/{collection_name}/status", response_model=FileStatusResponse)
async def get_file_status(collection_name: str, method: str = "auto") -> FileStatusResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.get_file_status,
        collection_name,
        method,
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

