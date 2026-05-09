from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from .database import Base, engine
from .router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="CodeSight Analysis Service",
    version="1.0.0",
    description="Сервис статического анализа: ruff, bandit, mypy",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
