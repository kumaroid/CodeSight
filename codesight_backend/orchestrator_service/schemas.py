"""Pydantic-схемы для API и Kafka-сообщений."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# API — запрос на запуск саги
# ---------------------------------------------------------------------------

ALL_STEPS = {"analysis", "security", "arch", "testing"}


class StartAnalysisRequest(BaseModel):
    project_id: str
    steps: list[str] = Field(
        default_factory=lambda: list(ALL_STEPS),
        description="Виды анализа: analysis, security, arch, testing",
    )

    def validated_steps(self) -> list[str]:
        unknown = set(self.steps) - ALL_STEPS
        if unknown:
            raise ValueError(f"Неизвестные шаги: {unknown}")
        return self.steps


# ---------------------------------------------------------------------------
# API — ответ
# ---------------------------------------------------------------------------


class SagaResponse(BaseModel):
    saga_id: str
    project_id: str
    status: str
    steps_status: dict[str, str]
    steps_run_ids: dict[str, str]
    error_message: str | None = None

    @classmethod
    def from_orm(cls, saga: Any) -> "SagaResponse":
        return cls(
            saga_id=saga.id,
            project_id=saga.project_id,
            status=saga.status,
            steps_status=json.loads(saga.steps_status),
            steps_run_ids=json.loads(saga.steps_run_ids),
            error_message=saga.error_message,
        )


# ---------------------------------------------------------------------------
# Kafka — командное сообщение (оркестратор → сервисы)
# ---------------------------------------------------------------------------


class AnalysisCommandMessage(BaseModel):
    """Команда на запуск одного из шагов."""

    saga_id: str
    project_id: str
    step: str  # analysis | security | arch | testing


# ---------------------------------------------------------------------------
# Kafka — результирующее сообщение (сервисы → оркестратор)
# ---------------------------------------------------------------------------


class AnalysisResultMessage(BaseModel):
    """Результат выполнения одного шага."""

    saga_id: str
    project_id: str
    step: str
    status: str  # completed | failed
    run_id: str | None = None
    error_message: str | None = None
