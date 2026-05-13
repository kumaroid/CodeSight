"""Точка входа оркестратора."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .kafka_client import stop_producer
from .router import router
from .saga import result_consumer_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CodeSight — Orchestrator Service",
    description=(
        "Сервис-оркестратор (паттерн Saga). "
        "Принимает задачу на анализ, распределяет её между сервисами через Kafka, "
        "собирает результаты и управляет компенсирующими транзакциями."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

_consumer_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    # Создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("БД оркестратора инициализирована")

    # Запускаем consumer в фоне
    global _consumer_task
    _consumer_task = asyncio.create_task(result_consumer_loop())
    logger.info("Kafka result consumer запущен")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _consumer_task is not None:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    await stop_producer()
    logger.info("Оркестратор остановлен")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "orchestrator"}


if __name__ == "__main__":
    uvicorn.run(
        "orchestrator_service.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
