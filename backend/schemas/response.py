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


class QuerySource(BaseModel):
    text: str
    page_idx: int
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[QuerySource] = Field(default_factory=list)


class FileStatusResponse(BaseModel):
    stage: Literal["none", "parsed", "translated", "indexed"]
    translated_path: str | None = None
    collection_name: str | None = None


class DeleteResponse(BaseModel):
    success: bool
    message: str
