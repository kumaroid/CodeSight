"""Бизнес-логика сервиса тестирования."""

from __future__ import annotations

import json
import os

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .config import settings
from .models import FileCoverage, TestResult, TestRun
from .runner import run_tests


async def start_test_run(
    project_id: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> TestRun:
    run = TestRun(project_id=project_id, status="pending")
    db.add(run)
    await db.commit()
    await db.refresh(run)
    background_tasks.add_task(_execute_test_run, run.id, project_id)
    return run


async def _execute_test_run(run_id: str, project_id: str) -> None:
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(TestRun, run_id)
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
            raw = await run_tests(project_path, timeout=settings.test_timeout)
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_message = str(exc)
            await db.commit()
            return

        # Заполняем метрики покрытия
        run.coverage_percent = raw.coverage_percent
        run.lines_total = raw.lines_total
        run.lines_covered = raw.lines_covered
        run.lines_missing = raw.lines_missing
        run.branches_total = raw.branches_total
        run.branches_covered = raw.branches_covered
        run.branch_coverage_percent = raw.branch_coverage_percent

        # Заполняем метрики тестов
        run.tests_total = raw.tests_total
        run.tests_passed = raw.tests_passed
        run.tests_failed = raw.tests_failed
        run.tests_error = raw.tests_error
        run.tests_skipped = raw.tests_skipped
        run.duration_seconds = raw.duration_seconds

        # Детализация по файлам
        for fc in raw.file_coverages:
            db.add(
                FileCoverage(
                    run_id=run_id,
                    file_path=fc.file_path,
                    lines_total=fc.lines_total,
                    lines_covered=fc.lines_covered,
                    lines_missing=fc.lines_missing,
                    coverage_percent=fc.coverage_percent,
                    missing_lines=json.dumps(fc.missing_lines),
                )
            )

        # Результаты отдельных тестов
        for tr in raw.test_results:
            db.add(
                TestResult(
                    run_id=run_id,
                    node_id=tr.node_id,
                    outcome=tr.outcome,
                    duration_seconds=tr.duration_seconds,
                    longrepr=tr.longrepr,
                )
            )

        run.status = "completed"
        await db.commit()


async def get_run(run_id: str, db: AsyncSession) -> TestRun:
    result = await db.execute(
        select(TestRun)
        .options(
            selectinload(TestRun.file_coverages),
            selectinload(TestRun.test_results),
        )
        .where(TestRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TestRun {run_id!r} не найден",
        )
    return run


async def list_runs_for_project(project_id: str, db: AsyncSession) -> list[TestRun]:
    result = await db.execute(
        select(TestRun)
        .where(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_run(run_id: str, db: AsyncSession) -> None:
    run = await db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TestRun {run_id!r} не найден",
        )
    await db.delete(run)
    await db.commit()
