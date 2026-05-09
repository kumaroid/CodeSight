from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import (
    AnalysisRunDetail,
    AnalysisRunListResponse,
    AnalysisRunOut,
    StartAnalysisRequest,
)
from .service import delete_run, get_run, list_runs_for_project, start_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/runs",
    response_model=AnalysisRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить статический анализ проекта",
)
async def create_run(
    body: StartAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunOut:
    """
    Принимает `project_id`, создаёт запись о запуске анализа (статус `pending`)
    и асинхронно запускает ruff + bandit + mypy в фоне.
    Возвращает объект запуска сразу — результаты появятся после завершения.
    """
    run = await start_analysis(body.project_id, db, background_tasks)
    return AnalysisRunOut.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=AnalysisRunDetail,
    summary="Получить результаты конкретного запуска",
)
async def get_run_by_id(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunDetail:
    """
    Возвращает запуск вместе со всеми найденными проблемами (`issues`).
    Если анализ ещё не завершён — `issues` будет пустым, а `status` — `running`.
    """
    run = await get_run(run_id, db)
    return AnalysisRunDetail.model_validate(run)


@router.get(
    "/projects/{project_id}/runs",
    response_model=AnalysisRunListResponse,
    summary="Список всех запусков анализа по проекту",
)
async def list_runs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunListResponse:
    runs = await list_runs_for_project(project_id, db)
    return AnalysisRunListResponse(
        items=[AnalysisRunOut.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запуск анализа",
)
async def remove_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_run(run_id, db)
