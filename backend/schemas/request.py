from typing import Literal

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    pdf_path: str
    method: Literal["auto", "txt", "ocr"] = "auto"
    lang: str = "en"
    formula: bool = True
    table: bool = True


class TranslateRequest(BaseModel):
    json_path: str
    src_lang: str = "en"
    tgt_lang: str = "chinese_cht"


class IndexRequest(BaseModel):
    json_path: str


class QueryRequest(BaseModel):
    question: str
    collection_name: str
    top_k: int = Field(default=10, ge=1)
