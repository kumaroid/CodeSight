"""Минимальный producer + фоновый consumer для топиков команд оркестратора.

Этот модуль устойчив к стартовой гонке (Kafka ещё не готова в момент запуска
сервиса) и к временным разрывам соединения: и producer, и consumer пытаются
переподключиться с экспоненциальной паузой, а не падают молча.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaError

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None
_producer_bootstrap: str | None = None
_producer_lock = asyncio.Lock()

# Сколько раз пытаемся запустить consumer/producer на старте сервиса.
_CONNECT_MAX_ATTEMPTS = 60
# Начальная и максимальная пауза между попытками подключения, секунды.
_CONNECT_BACKOFF_INITIAL = 1.0
_CONNECT_BACKOFF_MAX = 10.0


async def _start_with_retries(client: Any, label: str) -> None:
    """Стартовать Kafka client с ретраями на стартовой гонке."""
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


async def get_producer(bootstrap_servers: str) -> AIOKafkaProducer:
    global _producer, _producer_bootstrap
    async with _producer_lock:
        if _producer is None:
            _producer_bootstrap = bootstrap_servers
            _producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode(),
                acks="all",
            )
            await _start_with_retries(_producer, label=f"producer→{bootstrap_servers}")
            return _producer
        if bootstrap_servers != _producer_bootstrap:
            raise RuntimeError(
                "Kafka producer already bound to another bootstrap_servers"
            )
        return _producer


async def stop_shared_producer() -> None:
    global _producer, _producer_bootstrap
    async with _producer_lock:
        if _producer is not None:
            try:
                await _producer.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Ошибка при остановке Kafka producer")
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
    """Запускает бесконечный consumer; отмена task останавливает consumer.

    Реализует две стратегии устойчивости:
    1) Старт с ретраями — пока брокер не поднимется.
    2) Перезапуск всего цикла при необработанной ошибке транспорта/брокера,
       чтобы потеря соединения не «убивала» подписчика навсегда.
    """

    async def _loop() -> None:
        backoff = _CONNECT_BACKOFF_INITIAL
        while True:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda v: json.loads(v.decode()),
            )
            try:
                await _start_with_retries(consumer, label=f"consumer:{topic}")
            except Exception:
                logger.exception(
                    "Kafka consumer topic=%s: не удалось подняться, пауза %.1fс",
                    topic,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.7, _CONNECT_BACKOFF_MAX)
                continue
            logger.info("Kafka consumer started topic=%s group=%s", topic, group_id)
            backoff = _CONNECT_BACKOFF_INITIAL
            try:
                async for msg in consumer:
                    try:
                        await handler(msg.value)
                    except Exception:  # noqa: BLE001
                        logger.exception("Kafka handler error payload=%s", msg.value)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Kafka consumer topic=%s упал — перезапускаем", topic)
            finally:
                try:
                    await consumer.stop()
                except Exception:  # noqa: BLE001
                    logger.exception("Ошибка при остановке consumer topic=%s", topic)
                logger.info("Kafka consumer stopped topic=%s", topic)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.7, _CONNECT_BACKOFF_MAX)

    return asyncio.create_task(_loop(), name=f"kafka-consumer-{topic}")
