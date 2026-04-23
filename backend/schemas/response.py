from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ProgressMessage(BaseModel):
    type: Literal["progress"] = "progress"
    percent: float
    message: str


class ErrorCategory(str, Enum):
    REQUEST = "request"
    INPUT = "input"
    DEPENDENCY = "dependency"
    PIPELINE = "pipeline"
    SYSTEM = "system"
    NOT_IMPLEMENTED = "not_implemented"


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"

    code: str
    category: ErrorCategory
    message: str
    stage: str
    retryable: bool = False
    detail: str | None = None


class ParseResultMessage(BaseModel):
    type: Literal["result"] = "result"
    success: bool
    markdown_path: str | None = None
    json_path: str | None = None
    image_dir: str | None = None
    processing_time: float
    error: str = ""
    error_code: str | None = None
    error_category: ErrorCategory | None = None
    retryable: bool = False


class TranslateResultMessage(BaseModel):
    type: Literal["result"] = "result"
    success: bool
    translated_path: str | None = None
    translated_count: int = 0
    skipped_count: int = 0
    processing_time: float
    error: str = ""
    error_code: str | None = None
    error_category: ErrorCategory | None = None
    retryable: bool = False


class IndexResultMessage(BaseModel):
    type: Literal["result"] = "result"
    success: bool
    collection_name: str | None = None
    chunk_count: int = 0
    processing_time: float
    error: str = ""
    error_code: str | None = None
    error_category: ErrorCategory | None = None
    retryable: bool = False


class QuerySourceItem(BaseModel):
    page_idx: int
    type_v2: str
    text: str
    section_title: str
    chunk_id: str


class QuerySourcesMessage(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[QuerySourceItem] = Field(default_factory=list)


class QueryDeltaMessage(BaseModel):
    type: Literal["delta"] = "delta"
    delta: str


class QueryDoneMessage(BaseModel):
    type: Literal["done"] = "done"
    answer: str
    processing_time: float


class FileStatusResponse(BaseModel):
    stage: Literal["none", "parsed", "translated", "indexed"]
    translated_path: str | None = None
    collection_name: str | None = None


class DeleteResponse(BaseModel):
    success: bool
    message: str


class FileItem(BaseModel):
    name: str
    path: str


class FileListResponse(BaseModel):
    files: list[FileItem] = Field(default_factory=list)
