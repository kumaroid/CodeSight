from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .kafka_handlers import start_kafka, stop_kafka


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await start_kafka()
    yield
    await stop_kafka()


app = FastAPI(
    title="CodeSight DAST Service",
    version="1.0.0",
    description="Динамический анализ: Valgrind + Python (pytest --collect-only или smoke)",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dast"}
