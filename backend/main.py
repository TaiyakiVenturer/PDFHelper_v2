from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.http import router as http_router
from api.query import router as query_router
from api.ws import router as ws_router

HOST = "127.0.0.1"
PORT = 8080

_ARTIFACTS_DIR = str((Path(__file__).resolve().parent.parent / "data" / "artifacts").resolve())

app = FastAPI()

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
