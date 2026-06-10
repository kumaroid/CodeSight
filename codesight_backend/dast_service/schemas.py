"""Pydantic-схемы DAST."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DastFinding(BaseModel):
    """Одно конкретное наблюдение probe'а (форма edinaja для всех probes)."""

    severity: str  # error | warning | info
    rule: str
    file: str | None = None
    line: int | None = None
    message: str


class DastProbeResult(BaseModel):
    """Результат одного probe'а."""

    name: str
    status: str  # ok | warning | error | skipped | timeout
    duration_ms: int = 0
    summary: str = ""
    findings: list[DastFinding] = []
    metrics: dict[str, Any] = {}
    raw_tail: str = ""


class DastAggregate(BaseModel):
    """Сводка по запуску — то, что показываем в UI «крупными цифрами»."""

    total_probes: int = 0
    findings_total: int = 0
    findings_by_severity: dict[str, int] = {}
    probes_by_status: dict[str, int] = {}
    metrics: dict[str, Any] = {}


class DastRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    mode: str | None = None
    error_message: str | None = None
    command_summary: str | None = None

    # Структурированный отчёт.
    probes: list[DastProbeResult] = []
    aggregate: DastAggregate | None = None
    findings_total: int = 0
    findings_errors: int = 0
    findings_warnings: int = 0

    # Сырой лог. Дублируется в legacy-поле valgrind_report ради старого UI/API.
    raw_log: str | None = None
    valgrind_report: str | None = None

    created_at: datetime
    updated_at: datetime


class DastRunListResponse(BaseModel):
    items: list[DastRunOut]
    total: int
