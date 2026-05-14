"""Журнал событий саги (для UI и отладки)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect, text

from .database import AsyncSessionLocal, engine
from .models import SagaState

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 400


def _parse(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


async def append_activity(
    saga_id: str,
    message: str,
    *,
    level: str = "info",
    step: str | None = None,
) -> None:
    """Добавляет строку в activity_log саги (best-effort, не падает наружу)."""
    try:
        async with AsyncSessionLocal() as db:
            saga = await db.get(SagaState, saga_id)
            if saga is None:
                return
            log = _parse(getattr(saga, "activity_log", None))
            entry: dict[str, Any] = {
                "ts": datetime.now(UTC).isoformat(),
                "level": level,
                "message": message,
            }
            if step:
                entry["step"] = step
            log.append(entry)
            log = log[-_MAX_ENTRIES:]
            saga.activity_log = json.dumps(log, ensure_ascii=False)
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.debug("append_activity failed for saga=%s", saga_id, exc_info=True)


async def ensure_activity_log_column() -> None:
    """Добавляет колонку activity_log на существующих БД (create_all её не обновит)."""

    def _migrate(sync_conn: Any) -> None:
        insp = inspect(sync_conn)
        cols = [c["name"] for c in insp.get_columns("saga_states")]
        if "activity_log" in cols:
            return
        dialect = sync_conn.dialect.name
        if dialect == "postgresql":
            sync_conn.execute(
                text(
                    "ALTER TABLE saga_states ADD COLUMN IF NOT EXISTS activity_log "
                    "TEXT NOT NULL DEFAULT '[]'"
                )
            )
        else:
            sync_conn.execute(
                text(
                    "ALTER TABLE saga_states ADD COLUMN activity_log "
                    "TEXT NOT NULL DEFAULT '[]'"
                )
            )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(_migrate)
    except Exception:  # noqa: BLE001
        logger.warning("Не удалось добавить колонку activity_log", exc_info=True)
