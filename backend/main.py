import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.http import router as http_router
from api.query import router as query_router
from api.ws import router as ws_router

HOST = "127.0.0.1"
PORT = 8080

_ARTIFACTS_DIR = str((Path(__file__).resolve().parent.parent / "data" / "artifacts").resolve())

logger = logging.getLogger(__name__)


def _prewarm_one(name: str, fn) -> None:
    t0 = time.perf_counter()
    logger.info("[prewarm] 開始 import %s", name)
    fn()
    logger.info("[prewarm] 完成 import %s (%.2fs)", name, time.perf_counter() - t0)


def _prewarm_imports() -> None:
    """在背景執行緒 import 重型套件，暖機 sys.modules 快取。"""
    t_total = time.perf_counter()
    logger.info("[prewarm] 背景套件預熱開始")

    def _torch():
        import torch  # noqa: F401

    def _st():
        from sentence_transformers import SentenceTransformer  # noqa: F401

    def _llama():
        from llama_cpp import Llama  # noqa: F401

    def _hf():
        from huggingface_hub import hf_hub_download  # noqa: F401

    for name, fn in [("torch", _torch), ("sentence-transformers", _st), ("llama-cpp", _llama), ("huggingface-hub", _hf)]:
        try:
            _prewarm_one(name, fn)
        except ImportError:
            logger.warning("[prewarm] %s 未安裝，跳過", name)

    logger.info("[prewarm] 背景套件預熱完成，總耗時 %.2fs", time.perf_counter() - t_total)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(asyncio.to_thread(_prewarm_imports))
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(query_router)
app.include_router(http_router)
app.mount("/static/artifacts", StaticFiles(directory=_ARTIFACTS_DIR, html=False), name="artifacts")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
