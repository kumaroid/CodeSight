"""Обёртка над aiokafka: Producer и Consumer."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from .config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",
        )
        await _producer.start()
    return _producer


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
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
    """Создать consumer для переданных топиков."""
    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode()),
    )
