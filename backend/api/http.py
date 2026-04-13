import asyncio

from fastapi import APIRouter

from api.deps import get_orchestrator
from schemas.request import QueryRequest
from schemas.response import DeleteResponse
from schemas.response import FileStatusResponse
from schemas.response import QueryResponse

router = APIRouter()


@router.get("/file/{collection_name}/status", response_model=FileStatusResponse)
async def get_file_status(collection_name: str, method: str = "auto") -> FileStatusResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.get_file_status,
        collection_name,
        method,
    )


@router.delete("/file/{collection_name}", response_model=DeleteResponse)
async def delete_file(collection_name: str) -> DeleteResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.delete_file,
        collection_name,
    )


@router.post("/query", response_model=QueryResponse)
async def post_query(request: QueryRequest) -> QueryResponse:
    orchestrator = get_orchestrator()
    return await asyncio.to_thread(
        orchestrator.run_query,
        request.question,
        request.collection_name,
        request.top_k,
    )
