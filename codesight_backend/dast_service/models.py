import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


# Dialect-aware: на Postgres ложится в JSONB (индексируется, лучше для запросов),
# на SQLite/др. — обычный JSON (TEXT-backed). Логика моделей одинакова.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class DastRun(Base):
    """Запуск динамического анализа (probe-based).

    Поле ``valgrind_report`` сохранено для обратной совместимости со старым UI
    и API: туда теперь пишется тот же текст, что и в ``raw_log``.
    """

    __tablename__ = "dast_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "running", "completed", "failed", name="dast_run_status_enum"),
        nullable=False,
        default="pending",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # «Режим» прогона: pure-python / native+memcheck / limited.
    mode: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Структурированные результаты probes (см. runner.ProbeResult).
    probes: Mapped[list[dict[str, Any]] | None] = mapped_column(
        _JSON_TYPE, nullable=True
    )
    # Сводные счётчики/метрики (см. runner._aggregate).
    aggregate: Mapped[dict[str, Any] | None] = mapped_column(_JSON_TYPE, nullable=True)

    # Денормализованные счётчики для быстрых запросов и сортировки в UI.
    findings_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_warnings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Полный сырой лог (раньше — только вывод valgrind). Оставляем оба поля,
    # чтобы старые клиенты могли продолжать читать valgrind_report.
    raw_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    valgrind_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    command_summary: Mapped[str | None] = mapped_column(
        String(512), nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
