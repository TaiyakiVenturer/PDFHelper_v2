from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.http import router as http_router
from api.ws import router as ws_router

HOST = "127.0.0.1"
PORT = 8080


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
app.include_router(http_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
