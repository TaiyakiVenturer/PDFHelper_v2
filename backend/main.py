import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.parse import mineru_wrapper
from api.parse import router as parse_router

HOST = "127.0.0.1"
PORT = 8080


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(mineru_wrapper.startup)
    try:
        yield
    finally:
        await asyncio.to_thread(mineru_wrapper.shutdown)


app = FastAPI(lifespan=lifespan)
app.include_router(parse_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
