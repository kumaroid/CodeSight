"""Минимальный producer + фоновый consumer для топиков команд оркестратора."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None
_producer_bootstrap: str | None = None


async def get_producer(bootstrap_servers: str) -> AIOKafkaProducer:
    global _producer, _producer_bootstrap
    if _producer is None:
        _producer_bootstrap = bootstrap_servers
        _producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",
        )
        await _producer.start()
        return _producer
    if bootstrap_servers != _producer_bootstrap:
        raise RuntimeError("Kafka producer already bound to another bootstrap_servers")
    return _producer


async def stop_shared_producer() -> None:
    global _producer, _producer_bootstrap
    if _producer is not None:
        await _producer.stop()
        _producer = None
        _producer_bootstrap = None


async def send_json(
    bootstrap_servers: str,
    topic: str,
    payload: dict[str, Any],
    key: str | None = None,
) -> None:
    producer = await get_producer(bootstrap_servers)
    key_bytes = key.encode() if key else None
    await producer.send_and_wait(topic, value=payload, key=key_bytes)


def spawn_command_consumer(
    *,
    bootstrap_servers: str,
    topic: str,
    group_id: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
) -> asyncio.Task[None]:
    """Запускает бесконечный consumer; отмена task останавливает consumer."""

    async def _loop() -> None:
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        await consumer.start()
        logger.info("Kafka consumer started topic=%s group=%s", topic, group_id)
        try:
            async for msg in consumer:
                try:
                    await handler(msg.value)
                except Exception:  # noqa: BLE001
                    logger.exception("Kafka handler error payload=%s", msg.value)
        finally:
            await consumer.stop()
            logger.info("Kafka consumer stopped topic=%s", topic)

    return asyncio.create_task(_loop(), name=f"kafka-consumer-{topic}")
