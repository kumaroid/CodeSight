"""Логика саги: запуск шагов, обработка результатов, компенсация."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

from .activity_log import append_activity
from .config import settings
from .database import AsyncSessionLocal
from .kafka_client import make_consumer, send, start_consumer_with_retries
from .models import SagaState
from .schemas import AnalysisCommandMessage, AnalysisResultMessage

logger = logging.getLogger(__name__)

# Маппинг шага → топик команды
STEP_COMMAND_TOPIC: dict[str, str] = {
    "analysis": settings.topic_analysis_start,
    "security": settings.topic_security_start,
    "arch": settings.topic_arch_start,
    "testing": settings.topic_testing_start,
    "dast": settings.topic_dast_start,
}

# Топики результатов, за которыми слушает оркестратор
RESULT_TOPICS = [
    settings.topic_analysis_result,
    settings.topic_security_result,
    settings.topic_arch_result,
    settings.topic_testing_result,
    settings.topic_dast_result,
]

# Маппинг топика результата → имя шага
TOPIC_TO_STEP: dict[str, str] = {
    settings.topic_analysis_result: "analysis",
    settings.topic_security_result: "security",
    settings.topic_arch_result: "arch",
    settings.topic_testing_result: "testing",
    settings.topic_dast_result: "dast",
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

    await append_activity(
        saga.id,
        f"Сага запущена: шаги {', '.join(steps)}",
        level="info",
    )

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
        await append_activity(
            saga.id,
            f"Команда шага «{step}» отправлена в Kafka",
            level="info",
            step=step,
        )

    # Публикуем текущее состояние
    await _publish_state(saga.id)


# ---------------------------------------------------------------------------
# Фоновый consumer — слушает результаты всех сервисов
# ---------------------------------------------------------------------------


async def result_consumer_loop() -> None:
    """Бесконечный фоновый цикл, обрабатывающий результаты от сервисов.

    Устойчив к стартовой гонке Kafka и к временным разрывам соединения:
    consumer переподнимается с экспоненциальной паузой.
    """
    backoff = 1.0
    while True:
        consumer = make_consumer(*RESULT_TOPICS)
        try:
            await start_consumer_with_retries(consumer, label="orchestrator-results")
        except Exception:
            logger.exception("Оркестратор: не удалось поднять consumer, ретрай")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.7, 10.0)
            continue
        logger.info("Оркестратор: consumer запущен, слушает %s", RESULT_TOPICS)
        backoff = 1.0
        try:
            async for msg in consumer:
                step = TOPIC_TO_STEP.get(msg.topic, "unknown")
                with suppress(Exception):
                    await _handle_result(step, msg.value)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Оркестратор: consumer упал — перезапуск")
        finally:
            try:
                await consumer.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка при остановке consumer оркестратора")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 1.7, 10.0)


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
    await append_activity(
        result.saga_id,
        (
            f"Результат шага «{step}»: {result.status}"
            + (f" — {result.error_message}" if result.error_message else "")
        ),
        level="error" if result.status == "failed" else "info",
        step=step,
    )

    completed_all = False
    async with AsyncSessionLocal() as db:
        saga = await db.get(SagaState, result.saga_id)
        if saga is None:
            logger.warning(
                "Сага %s не найдена (результат шага %s)", result.saga_id, step
            )
            return

        # Если сага уже отменена/компенсируется — не перетираем "cancelled"
        # статусы шагов; только сохраняем run_id (вдруг понадобится компенсация).
        if saga.status in ("compensating", "compensated"):
            if result.run_id:
                steps_run_ids: dict[str, str] = json.loads(saga.steps_run_ids)
                steps_run_ids[step] = result.run_id
                saga.steps_run_ids = json.dumps(steps_run_ids)
                await db.commit()
                await _publish_state(result.saga_id)
            return

        steps_status: dict[str, str] = json.loads(saga.steps_status)
        steps_run_ids = json.loads(saga.steps_run_ids)

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
            completed_all = all(steps_status.get(s) == "completed" for s in requested)
            if completed_all:
                saga.status = "completed"

        await db.commit()

    if completed_all:
        await append_activity(
            result.saga_id,
            "Все запрошенные шаги анализа успешно завершены",
            level="info",
        )

    await _publish_state(result.saga_id)


# ---------------------------------------------------------------------------
# Отмена саги пользователем
# ---------------------------------------------------------------------------


async def cancel_saga(saga_id: str, reason: str | None = None) -> SagaState | None:
    """
    Отменить выполняющуюся сагу.

    Запущенные/ожидающие шаги помечаются как "cancelled" — поздние результаты
    от воркеров будут проигнорированы в `_handle_result`. Для уже завершённых
    шагов отправляются компенсационные команды.
    """
    async with AsyncSessionLocal() as db:
        saga = await db.get(SagaState, saga_id)
        if saga is None:
            return None
        if saga.status in ("completed", "failed", "compensated"):
            return saga  # уже терминальное состояние

        steps_status: dict[str, str] = json.loads(saga.steps_status)
        for step, st in list(steps_status.items()):
            if st in ("pending", "running"):
                steps_status[step] = "cancelled"
        saga.steps_status = json.dumps(steps_status)
        saga.status = "compensating"
        saga.error_message = reason or "Отменено пользователем"
        await db.commit()
        await db.refresh(saga)

    await append_activity(
        saga_id,
        reason or "Пользователь остановил анализ (отмена саги)",
        level="warning",
    )

    await _compensate(saga)
    return saga


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
        await append_activity(
            saga.id,
            f"Отправлено компенсационных команд: {len(tasks)}",
            level="warning",
        )

    async with AsyncSessionLocal() as db:
        db_saga = await db.get(SagaState, saga.id)
        if db_saga:
            db_saga.status = "compensated"
            await db.commit()

    await append_activity(
        saga.id,
        "Компенсация завершена, сага закрыта",
        level="info",
    )

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
