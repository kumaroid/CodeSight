"""Обработка команд Kafka от оркестратора (шаг analysis)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from codesight_backend.kafka_common.client import (
    send_json,
    spawn_command_consumer,
    stop_shared_producer,
)

from .config import settings
from .database import AsyncSessionLocal
from .models import AnalysisRun
from .service import _execute_analysis

logger = logging.getLogger(__name__)

_kafka_task: asyncio.Task[None] | None = None


async def start_kafka() -> None:
    global _kafka_task
    if _kafka_task is not None:
        return
    _kafka_task = spawn_command_consumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic_command,
        group_id=settings.kafka_consumer_group,
        handler=_handle_command,
    )


async def stop_kafka() -> None:
    global _kafka_task
    if _kafka_task is not None:
        _kafka_task.cancel()
        try:
            await _kafka_task
        except asyncio.CancelledError:
            pass
        _kafka_task = None
    await stop_shared_producer()


async def _handle_command(payload: dict[str, Any]) -> None:
    saga_id = payload.get("saga_id")
    project_id = payload.get("project_id")
    if not saga_id or not project_id:
        logger.warning("Некорректное сообщение: %s", payload)
        return

    run_id: str | None = None
    status = "failed"
    err: str | None = "unknown error"

    try:
        async with AsyncSessionLocal() as db:
            run = AnalysisRun(project_id=project_id, status="pending")
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id

        await _execute_analysis(run_id, project_id)

        async with AsyncSessionLocal() as db:
            run = await db.get(AnalysisRun, run_id)
        if run is None:
            err = "run record lost"
        else:
            status = "completed" if run.status == "completed" else "failed"
            err = run.error_message if status == "failed" else None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка анализа по Kafka")
        err = str(exc)

    await send_json(
        settings.kafka_bootstrap_servers,
        settings.kafka_topic_result,
        {
            "saga_id": saga_id,
            "project_id": project_id,
            "status": status,
            "run_id": run_id,
            "error_message": err,
        },
        key=saga_id,
    )
