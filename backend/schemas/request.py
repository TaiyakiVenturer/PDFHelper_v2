from typing import Literal

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    collection_name: str
    method: Literal["auto", "txt", "ocr"] = "auto"
    lang: str = "en"
    formula: bool = True
    table: bool = True


class TranslateRequest(BaseModel):
    collection_name: str
    method: Literal["auto", "txt", "ocr"] = "auto"
    src_lang: str = "en"
    tgt_lang: str = "chinese_cht"


class IndexRequest(BaseModel):
    collection_name: str
    method: Literal["auto", "txt", "ocr"] = "auto"


class QueryRequest(BaseModel):
    question: str
    collection_name: str
    top_k: int = Field(default=5, ge=1)
    history: list[dict[str, str]] = Field(default_factory=list)


class UploadFileRequest(BaseModel):
    source_path: str
