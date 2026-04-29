from __future__ import annotations

from pathlib import Path


CHUNK_TOKEN_LIMIT = 512
EMBEDDING_BATCH_SIZE = 4

HF_REPO_ID = "BAAI/bge-m3"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[3] / "models"

CHROMA_PERSIST_SUBDIR = "chroma"
TIKTOKEN_ENCODING = "cl100k_base"
SPLIT_BOUNDARY_PUNCTUATION = (
    "。",
    ".",
    "？",
    "?",
    "！",
    "!",
    "；",
    ";",
    "，",
    ",",
    " ",
)