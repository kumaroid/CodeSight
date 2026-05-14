"""ORM-модели для оркестратора (хранение состояния саги)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class SagaState(Base):
    """
    Состояние саги анализа.

    Жизненный цикл:
        PENDING → RUNNING → COMPLETED | FAILED | COMPENSATING → COMPENSATED
    """

    __tablename__ = "saga_states"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Запрошенные виды анализа, хранятся как JSON-строка: '["analysis","security"]'
    requested_steps: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]"
    )  # JSON

    # Статус каждого шага — тоже JSON: '{"analysis": "pending", "security": "running"}'
    steps_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )  # JSON

    # Итоговые run_id от каждого сервиса: '{"analysis": "<uuid>", "security": "<uuid>"}'
    steps_run_ids: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )  # JSON

    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "running",
            "completed",
            "failed",
            "compensating",
            "compensated",
            name="saga_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON-массив событий для UI: [{"ts":"...","level":"info","step":"analysis","message":"..."}, ...]
    activity_log: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
