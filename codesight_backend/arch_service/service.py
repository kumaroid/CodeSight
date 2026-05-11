"""Бизнес-логика сервиса архитектурного анализа."""

from __future__ import annotations

import os

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .analyzer import analyze_plantuml
from .models import ArchRecommendation, ArchRun, ComponentMetric


async def start_arch_analysis(
    project_id: str,
    plantuml_text: str,
    db: AsyncSession,
) -> tuple[ArchRun, dict]:
    """Синхронно анализирует PlantUML и сохраняет результаты."""
    run = ArchRun(project_id=project_id, status="running")
    db.add(run)
    await db.flush()  # получаем run.id

    try:
        metrics, recommendations, summary = analyze_plantuml(plantuml_text)
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(exc)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ошибка парсинга PlantUML: {exc}",
        ) from exc

    for m in metrics:
        db.add(
            ComponentMetric(
                run_id=run.id,
                component=m.component,
                ca=m.ca,
                ce=m.ce,
                instability=m.instability,
                coupling_score=m.coupling_score,
                cohesion_score=m.cohesion_score,
            )
        )

    for r in recommendations:
        db.add(
            ArchRecommendation(
                run_id=run.id,
                severity=r.severity,
                component=r.component,
                rule=r.rule,
                message=r.message,
            )
        )

    run.status = "completed"
    await db.commit()
    await db.refresh(run)
    return run, summary


async def get_run(
    run_id: str,
    db: AsyncSession,
) -> ArchRun:
    result = await db.execute(
        select(ArchRun)
        .options(
            selectinload(ArchRun.metrics),
            selectinload(ArchRun.recommendations),
        )
        .where(ArchRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ArchRun {run_id!r} не найден",
        )
    return run


async def list_runs_for_project(
    project_id: str,
    db: AsyncSession,
) -> list[ArchRun]:
    result = await db.execute(
        select(ArchRun)
        .where(ArchRun.project_id == project_id)
        .order_by(ArchRun.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_run(
    run_id: str,
    db: AsyncSession,
) -> None:
    run = await db.get(ArchRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ArchRun {run_id!r} не найден",
        )
    await db.delete(run)
    await db.commit()


def _load_first_plantuml(project_root: str) -> str | None:
    """Ищет PlantUML: приоритетные имена, затем любой .puml в дереве."""
    preferred = (
        "diagram.puml",
        "architecture.puml",
        os.path.join("docs", "diagram.puml"),
    )
    for rel in preferred:
        path = os.path.join(project_root, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read()
    for root, _, files in os.walk(project_root):
        for name in files:
            if name.endswith(".puml"):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    return fh.read()
    return None


async def run_arch_analysis_from_workspace(
    project_id: str,
) -> tuple[str, str, str | None]:
    """
    Запуск из Kafka: читает PlantUML с диска (тот же volume, что у loader).
    Возвращает (run_id, status, error_message).
    """
    from .config import settings
    from .database import AsyncSessionLocal

    base = os.path.join(settings.project_storage_dir, project_id)
    if not os.path.isdir(base):
        return "", "failed", f"Директория проекта не найдена: {base}"

    text = _load_first_plantuml(base)
    async with AsyncSessionLocal() as db:
        if not text:
            run = ArchRun(
                project_id=project_id,
                status="completed",
                error_message="Файл .puml не найден; шаг пропущен без метрик.",
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            return run.id, "completed", None
        try:
            run, _summary = await start_arch_analysis(project_id, text, db)
        except HTTPException as exc:
            detail = str(exc.detail)
            async with AsyncSessionLocal() as db2:
                r = await db2.execute(
                    select(ArchRun)
                    .where(ArchRun.project_id == project_id)
                    .order_by(ArchRun.created_at.desc())
                    .limit(1)
                )
                last = r.scalar_one_or_none()
            rid = last.id if last else ""
            return rid, "failed", detail
        except Exception as exc:  # noqa: BLE001
            return "", "failed", str(exc)
        else:
            return run.id, run.status, run.error_message
