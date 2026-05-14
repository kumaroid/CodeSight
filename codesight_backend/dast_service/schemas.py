"""Pydantic-схемы DAST."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DastRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    error_message: str | None = None
    valgrind_report: str | None = None
    command_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class DastRunListResponse(BaseModel):
    items: list[DastRunOut]
    total: int
