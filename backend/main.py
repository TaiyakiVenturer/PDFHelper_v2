from fastapi import FastAPI

from api.http import router as http_router
from api.ws import router as ws_router

HOST = "127.0.0.1"
PORT = 8080


app = FastAPI()
app.include_router(ws_router)
app.include_router(http_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
