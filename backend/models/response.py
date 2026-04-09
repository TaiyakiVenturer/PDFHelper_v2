from typing import Literal

from pydantic import BaseModel, Field


class ProgressMessage(BaseModel):
    type: Literal["progress"] = "progress"
    percent: float
    message: str


class ResultMessage(BaseModel):
    type: Literal["result"] = "result"
    success: bool
    markdown_path: str | None = None
    json_path: str | None = None
    image_path: list[str] = Field(default_factory=list)
    processing_time: float
    error: str = ""


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    error: str
