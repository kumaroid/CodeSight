from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .kafka_handlers import start_kafka, stop_kafka
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await start_kafka()
    yield
    await stop_kafka()


app = FastAPI(
    title="CodeSight Security Service",
    version="1.0.0",
    description="Сервис проверки безопасности кода по модели OWASP Top 10 (bandit + regex + pip-audit)",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "security"}
