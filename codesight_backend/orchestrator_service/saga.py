"""Логика саги: запуск шагов, обработка результатов, компенсация."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

from .config import settings
from .database import AsyncSessionLocal
from .kafka_client import make_consumer, send
from .models import SagaState
from .schemas import AnalysisCommandMessage, AnalysisResultMessage

logger = logging.getLogger(__name__)

# Маппинг шага → топик команды
STEP_COMMAND_TOPIC: dict[str, str] = {
    "analysis": settings.topic_analysis_start,
    "security": settings.topic_security_start,
    "arch":     settings.topic_arch_start,
    "testing":  settings.topic_testing_start,
}

# Топики результатов, за которыми слушает оркестратор
RESULT_TOPICS = [
    settings.topic_analysis_result,
    settings.topic_security_result,
    settings.topic_arch_result,
    settings.topic_testing_result,
]

# Маппинг топика результата → имя шага
TOPIC_TO_STEP: dict[str, str] = {
    settings.topic_analysis_result: "analysis",
    settings.topic_security_result: "security",
    settings.topic_arch_result:     "arch",
    settings.topic_testing_result:  "testing",
}


# ---------------------------------------------------------------------------
# Публичный API — запуск саги
# ---------------------------------------------------------------------------


async def start_saga(saga: SagaState) -> None:
    """
    Запустить новую сагу: отправить команды всем запрошенным шагам в Kafka.
    Вызывается сразу после создания записи SagaState.
    """
    steps: list[str] = json.loads(saga.requested_steps)
    steps_status: dict[str, str] = {s: "pending" for s in steps}

    async with AsyncSessionLocal() as db:
        db_saga = await db.get(SagaState, saga.id)
        if db_saga is None:
            logger.error("Сага %s не найдена в БД при старте", saga.id)
            return
        db_saga.status = "running"
        db_saga.steps_status = json.dumps(steps_status)
        await db.commit()

    for step in steps:
        topic = STEP_COMMAND_TOPIC.get(step)
        if topic is None:
            logger.warning("Неизвестный шаг %s — пропускаем", step)
            continue
        msg = AnalysisCommandMessage(
            saga_id=saga.id,
            project_id=saga.project_id,
            step=step,
        )
        await send(topic, msg.model_dump(), key=saga.id)
        logger.info("Сага %s: отправлена команда '%s'", saga.id, step)

    # Публикуем текущее состояние
    await _publish_state(saga.id)


# ---------------------------------------------------------------------------
# Фоновый consumer — слушает результаты всех сервисов
# ---------------------------------------------------------------------------


async def result_consumer_loop() -> None:
    """Бесконечный фоновый цикл, обрабатывающий результаты от сервисов."""
    consumer = make_consumer(*RESULT_TOPICS)
    await consumer.start()
    logger.info("Оркестратор: consumer запущен, слушает %s", RESULT_TOPICS)
    try:
        async for msg in consumer:
            step = TOPIC_TO_STEP.get(msg.topic, "unknown")
            with suppress(Exception):
                await _handle_result(step, msg.value)
    finally:
        await consumer.stop()


async def _handle_result(step: str, payload: dict) -> None:
    """Обработать одно результирующее сообщение от сервиса."""
    try:
        result = AnalysisResultMessage(
            saga_id=payload["saga_id"],
            project_id=payload["project_id"],
            step=step,
            status=payload["status"],
            run_id=payload.get("run_id"),
            error_message=payload.get("error_message"),
        )
    except (KeyError, TypeError) as exc:
        logger.error("Неверный формат результата: %s — %s", payload, exc)
        return

    logger.info(
        "Сага %s: получен результат шага '%s' → %s",
        result.saga_id,
        step,
        result.status,
    )

    async with AsyncSessionLocal() as db:
        saga = await db.get(SagaState, result.saga_id)
        if saga is None:
            logger.warning("Сага %s не найдена (результат шага %s)", result.saga_id, step)
            return

        steps_status: dict[str, str] = json.loads(saga.steps_status)
        steps_run_ids: dict[str, str] = json.loads(saga.steps_run_ids)

        steps_status[step] = result.status
        if result.run_id:
            steps_run_ids[step] = result.run_id

        saga.steps_status = json.dumps(steps_status)
        saga.steps_run_ids = json.dumps(steps_run_ids)

        if result.status == "failed":
            # Хотя бы один шаг упал → компенсация
            if saga.status not in ("failed", "compensating", "compensated"):
                saga.status = "compensating"
                saga.error_message = (
                    f"Шаг '{step}' завершился с ошибкой: {result.error_message}"
                )
                await db.commit()
                await _compensate(saga)
                return
        else:
            # Проверяем, завершены ли все запрошенные шаги
            requested: list[str] = json.loads(saga.requested_steps)
            all_done = all(steps_status.get(s) == "completed" for s in requested)
            if all_done:
                saga.status = "completed"

        await db.commit()

    await _publish_state(result.saga_id)


# ---------------------------------------------------------------------------
# Компенсация
# ---------------------------------------------------------------------------


async def _compensate(saga: SagaState) -> None:
    """
    Паттерн Saga (оркестратор) — компенсирующие транзакции.

    Для каждого шага, который уже завершился успешно, отправляем
    команду отмены (компенсации) в соответствующий сервис.
    Сервисы должны слушать топики `codesight.<step>.compensate`.
    """
    steps_status: dict[str, str] = json.loads(saga.steps_status)
    steps_run_ids: dict[str, str] = json.loads(saga.steps_run_ids)

    tasks: list[asyncio.coroutine] = []
    for step, status in steps_status.items():
        if status == "completed" and step in steps_run_ids:
            compensate_topic = f"codesight.{step}.compensate"
            payload = {
                "saga_id": saga.id,
                "project_id": saga.project_id,
                "step": step,
                "run_id": steps_run_ids[step],
            }
            tasks.append(send(compensate_topic, payload, key=saga.id))
            logger.info("Сага %s: отправлена компенсация для шага '%s'", saga.id, step)

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    async with AsyncSessionLocal() as db:
        db_saga = await db.get(SagaState, saga.id)
        if db_saga:
            db_saga.status = "compensated"
            await db.commit()

    await _publish_state(saga.id)


# ---------------------------------------------------------------------------
# Публикация состояния саги в отдельный топик
# ---------------------------------------------------------------------------


async def _publish_state(saga_id: str) -> None:
    """Отправить актуальное состояние саги в топик saga_state."""
    async with AsyncSessionLocal() as db:
        saga = await db.get(SagaState, saga_id)
        if saga is None:
            return
        payload = {
            "saga_id": saga.id,
            "project_id": saga.project_id,
            "status": saga.status,
            "steps_status": json.loads(saga.steps_status),
            "steps_run_ids": json.loads(saga.steps_run_ids),
            "error_message": saga.error_message,
        }
    await send(settings.topic_saga_state, payload, key=saga_id)
