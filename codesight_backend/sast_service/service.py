"""Бизнес-логика сервиса статического анализа."""

from __future__ import annotations

import os

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .analyzers import run_all
from .config import settings
from .models import AnalysisRun, Issue


async def start_analysis(
    project_id: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> AnalysisRun:
    """Создать запись о запуске анализа и поставить задачу в фон."""
    run = AnalysisRun(project_id=project_id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(_execute_analysis, run.id, project_id)
    return run


async def _execute_analysis(run_id: str, project_id: str) -> None:
    """Фоновая задача: запустить анализаторы и сохранить результаты."""
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(AnalysisRun, run_id)
        if run is None:
            return

        project_path = os.path.join(settings.storage_dir, project_id)
        if not os.path.isdir(project_path):
            run.status = "failed"
            run.error_message = f"Директория проекта не найдена: {project_path}"
            await db.commit()
            return

        run.status = "running"
        await db.commit()

        try:
            raw_issues = await run_all(project_path)
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_message = str(exc)
            await db.commit()
            return

        for raw in raw_issues:
            issue = Issue(
                run_id=run_id,
                tool=raw.tool,
                severity=raw.severity,
                file_path=raw.file_path,
                line=raw.line,
                column=raw.column,
                code=raw.code,
                message=raw.message,
            )
            db.add(issue)

        run.status = "completed"
        await db.commit()


async def get_run(
    run_id: str,
    db: AsyncSession,
) -> AnalysisRun:
    result = await db.execute(
        select(AnalysisRun)
        .options(selectinload(AnalysisRun.issues))
        .where(AnalysisRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AnalysisRun {run_id!r} не найден",
        )
    return run


async def list_runs_for_project(
    project_id: str,
    db: AsyncSession,
) -> list[AnalysisRun]:
    result = await db.execute(
        select(AnalysisRun)
        .where(AnalysisRun.project_id == project_id)
        .order_by(AnalysisRun.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_run(
    run_id: str,
    db: AsyncSession,
) -> None:
    run = await db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AnalysisRun {run_id!r} не найден",
        )
    await db.delete(run)
    await db.commit()
