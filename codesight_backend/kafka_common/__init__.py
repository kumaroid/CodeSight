"""Общие утилиты Kafka для микросервисов-воркеров (команда → обработка → результат)."""

from codesight_backend.kafka_common.client import (
    send_json,
    spawn_command_consumer,
    stop_shared_producer,
)

__all__ = ["send_json", "spawn_command_consumer", "stop_shared_producer"]
