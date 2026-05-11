import asyncio
from contextlib import asynccontextmanager
import logging
import os

# Windows: add PyTorch's lib dir to DLL search path so llama-cpp-python
# can find CUDA runtime DLLs (cudart, cublas) bundled with torch.
# This must run before any import that transitively loads llama.dll.
if os.name == 'nt':
    try:
        import torch as _torch
        _torch_lib = os.path.join(os.path.dirname(_torch.__file__), 'lib')
        if os.path.isdir(_torch_lib):
            os.add_dll_directory(_torch_lib)
        del _torch, _torch_lib
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.http import router as http_router
from api.query import router as query_router
from api.ws import router as ws_router
from core.paths import DATA_DIR
from core.prewarm import prewarm_imports
from core.watcher import start_parent_watcher

HOST = "127.0.0.1"
PORT = 12230

_ARTIFACTS_DIR = str(DATA_DIR / "artifacts")

_ALLOWED_ORIGINS = [
    "http://localhost:1420",
    "http://127.0.0.1:1420",
    "http://tauri.localhost",    # Tauri production (Windows/WebView2)
    "tauri://localhost",        # Tauri production (macOS/Linux)
]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[paths] Data location: %s", DATA_DIR)
    logger.info("[cors] Allowed origins: %s", _ALLOWED_ORIGINS)
    start_parent_watcher()
    asyncio.create_task(asyncio.to_thread(prewarm_imports))
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_origin(request: Request, call_next):
    origin = request.headers.get("origin", "<no origin>")
    logger.info("[cors] %s %s  origin=%s", request.method, request.url.path, origin)
    response = await call_next(request)
    acao = response.headers.get("access-control-allow-origin", "<not set>")
    logger.info("[cors] response  access-control-allow-origin=%s", acao)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
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
