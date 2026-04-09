from typing import Literal

from pydantic import BaseModel


class ParseRequest(BaseModel):
    pdf_path: str
    method: Literal["auto", "txt", "ocr"] = "auto"
    lang: str = "en"
    formula: bool = True
    table: bool = True
