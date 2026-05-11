"""Обработка команд Kafka (шаг dast)."""

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
from .service import start_dast_run_for_kafka

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

    try:
        run_id, status, err = await start_dast_run_for_kafka(project_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка dast по Kafka")
        run_id, status, err = "", "failed", str(exc)

    await send_json(
        settings.kafka_bootstrap_servers,
        settings.kafka_topic_result,
        {
            "saga_id": saga_id,
            "project_id": project_id,
            "status": status,
            "run_id": run_id or None,
            "error_message": err,
        },
        key=saga_id,
    )
