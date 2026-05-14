"""Обёртка над aiokafka: Producer и Consumer с ретраями подключения."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError

from .config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None
_producer_lock = asyncio.Lock()

_CONNECT_MAX_ATTEMPTS = 60
_CONNECT_BACKOFF_INITIAL = 1.0
_CONNECT_BACKOFF_MAX = 10.0


async def _start_with_retries(client: Any, label: str) -> None:
    backoff = _CONNECT_BACKOFF_INITIAL
    last_exc: BaseException | None = None
    for attempt in range(1, _CONNECT_MAX_ATTEMPTS + 1):
        try:
            await client.start()
            if attempt > 1:
                logger.info("Kafka %s подключён со %d попытки", label, attempt)
            return
        except (KafkaConnectionError, KafkaError, OSError) as exc:
            last_exc = exc
            logger.warning(
                "Kafka %s: попытка %d/%d не удалась (%s), пауза %.1fс",
                label,
                attempt,
                _CONNECT_MAX_ATTEMPTS,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.7, _CONNECT_BACKOFF_MAX)
    raise RuntimeError(
        f"Kafka {label}: не удалось подключиться за {_CONNECT_MAX_ATTEMPTS} попыток"
    ) from last_exc


async def get_producer() -> AIOKafkaProducer:
    global _producer
    async with _producer_lock:
        if _producer is None:
            _producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode(),
                acks="all",
            )
            await _start_with_retries(
                _producer, label=f"producer→{settings.kafka_bootstrap_servers}"
            )
        return _producer


async def stop_producer() -> None:
    global _producer
    async with _producer_lock:
        if _producer is not None:
            try:
                await _producer.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка при остановке Kafka producer")
            _producer = None


async def send(
    topic: str,
    payload: dict[str, Any],
    key: str | None = None,
) -> None:
    """Отправить JSON-сообщение в Kafka."""
    producer = await get_producer()
    key_bytes = key.encode() if key else None
    await producer.send_and_wait(topic, value=payload, key=key_bytes)
    logger.debug("Kafka → %s: %s", topic, payload)


def make_consumer(*topics: str) -> AIOKafkaConsumer:
    """Создать consumer для переданных топиков (без start)."""
    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode()),
    )


async def start_consumer_with_retries(consumer: AIOKafkaConsumer, label: str) -> None:
    """Поднять consumer оркестратора с ретраями на стартовой гонке."""
    await _start_with_retries(consumer, label=label)
