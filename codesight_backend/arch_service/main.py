from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import Base, engine
from .kafka_handlers import start_kafka, stop_kafka
from .router import router


async def _apply_runtime_migrations(conn) -> None:
    """Лёгкие идемпотентные миграции, не покрытые ``create_all``.

    После того как cohesion_score стал ``NULL``-аware (изолированные модули
    больше не получают фолбэк 1.0), существующие БД, созданные ранее с
    ``NOT NULL``, отвергают новые записи. На Postgres снимаем ограничение
    одной командой; на SQLite ALTER COLUMN не поддерживается — пропускаем
    (там колонка по факту не enforce'ит ``NOT NULL`` после рестарта схемы).
    """
    if conn.dialect.name != "postgresql":
        return
    await conn.execute(
        text("ALTER TABLE component_metrics ALTER COLUMN cohesion_score DROP NOT NULL")
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_runtime_migrations(conn)
    await start_kafka()
    yield
    await stop_kafka()


app = FastAPI(
    title="CodeSight Architecture Service",
    version="1.0.0",
    description="Анализ архитектуры проекта: парсинг PlantUML, метрики Coupling и Cohesion, рекомендации",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "arch"}
