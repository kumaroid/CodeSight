from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db
from .models import ArchRun
from .schemas import (
    ArchRunDetail,
    ArchRunListResponse,
    ArchRunOut,
    StartArchRequest,
)
from .service import delete_run, get_run, list_runs_for_project, start_arch_analysis

router = APIRouter(prefix="/arch", tags=["architecture"])


@router.post(
    "/analyze",
    response_model=ArchRunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Проанализировать PlantUML-диаграмму архитектуры",
)
async def analyze(
    body: StartArchRequest,
    db: AsyncSession = Depends(get_db),
) -> ArchRunDetail:
    """
    Принимает `project_id` и `plantuml` (текст диаграммы зависимостей).
    Вычисляет метрики Coupling (Ca, Ce, Instability, coupling_score)
    и Cohesion (cohesion_score) для каждого компонента.
    Возвращает метрики, рекомендации и summary с итоговым health-score.
    """
    run, summary = await start_arch_analysis(body.project_id, body.plantuml, db)
    # Подгружаем связи
    result = await db.execute(
        select(ArchRun)
        .options(
            __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(
                ArchRun.metrics
            ),
            __import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(
                ArchRun.recommendations
            ),
        )
        .where(ArchRun.id == run.id)
    )
    run = result.scalar_one()
    detail = ArchRunDetail.model_validate(run)
    detail.summary = summary
    return detail


@router.get(
    "/runs/{run_id}",
    response_model=ArchRunDetail,
    summary="Получить результаты архитектурного анализа",
)
async def get_run_by_id(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArchRunDetail:
    run = await get_run(run_id, db)
    detail = ArchRunDetail.model_validate(run)
    return detail


@router.get(
    "/projects/{project_id}/runs",
    response_model=ArchRunListResponse,
    summary="Список всех запусков архитектурного анализа по проекту",
)
async def list_runs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ArchRunListResponse:
    runs = await list_runs_for_project(project_id, db)
    return ArchRunListResponse(
        items=[ArchRunOut.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запуск архитектурного анализа",
)
async def remove_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_run(run_id, db)
