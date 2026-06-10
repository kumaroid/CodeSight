import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import Base, engine
from .kafka_handlers import start_kafka, stop_kafka
from .router import router

logger = logging.getLogger(__name__)


# Список колонок, которые могут отсутствовать в старой таблице ``dast_runs``,
# созданной до перехода на probe-based архитектуру. ``create_all`` не делает
# ALTER, поэтому добавляем их вручную, идемпотентно. Все новые поля nullable
# или имеют DEFAULT, так что миграция не требует backfill.
_DAST_ADDITIVE_COLUMNS: list[tuple[str, str]] = [
    ("mode", "VARCHAR(64)"),
    ("probes", "JSONB"),
    ("aggregate", "JSONB"),
    ("findings_total", "INTEGER NOT NULL DEFAULT 0"),
    ("findings_errors", "INTEGER NOT NULL DEFAULT 0"),
    ("findings_warnings", "INTEGER NOT NULL DEFAULT 0"),
    ("raw_log", "TEXT"),
]


async def _apply_runtime_migrations(conn) -> None:
    """Идемпотентные миграции, не покрытые ``create_all``.

    Используется ``ADD COLUMN IF NOT EXISTS`` (Postgres ≥ 9.6). На SQLite
    миграция пропускается: ALTER TABLE с JSON-типом там либо ограничен,
    либо ``create_all`` уже создал свежую таблицу под актуальный набор колонок.
    """
    if conn.dialect.name != "postgresql":
        return
    for col, ddl in _DAST_ADDITIVE_COLUMNS:
        stmt = f"ALTER TABLE dast_runs ADD COLUMN IF NOT EXISTS {col} {ddl}"
        try:
            await conn.execute(text(stmt))
        except Exception as exc:  # noqa: BLE001
            # Логируем, но не валим старт сервиса — на новой БД эти ALTER
            # просто no-op после create_all.
            logger.warning("dast_runs migration skipped (%s): %s", col, exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_runtime_migrations(conn)
    await start_kafka()
    yield
    await stop_kafka()


app = FastAPI(
    title="CodeSight DAST Service",
    version="1.0.0",
    description=(
        "Динамический анализ Python-проектов: набор probes "
        "(bytecode_compile, smoke_imports, pytest_collect, resource_profile, "
        "pip_check, valgrind_memcheck) с агрегированными метриками."
    ),
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
    return {"status": "ok", "service": "dast"}
