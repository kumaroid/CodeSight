from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from .completeness import analyze_completeness
from .config import settings
from .database import get_db
from .schemas import (
    StartTestRunRequest,
    TestRunDetail,
    TestRunListResponse,
    TestRunOut,
)
from .service import delete_run, get_run, list_runs_for_project, start_test_run
import os

router = APIRouter(prefix="/testing", tags=["testing"])


@router.post(
    "/runs",
    response_model=TestRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить тестирование проекта",
)
async def create_run(
    body: StartTestRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> TestRunOut:
    """
    Запускает `pytest --cov` в директории проекта асинхронно.
    Возвращает объект запуска сразу — результаты появятся после завершения.
    """
    run = await start_test_run(body.project_id, db, background_tasks)
    return TestRunOut.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=TestRunDetail,
    summary="Получить результаты запуска с деталями",
)
async def get_run_by_id(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> TestRunDetail:
    """
    Возвращает полную детализацию: метрики покрытия, покрытие по файлам
    и результаты каждого теста (passed/failed/skipped).
    """
    run = await get_run(run_id, db)
    return TestRunDetail.model_validate(run)


@router.get(
    "/projects/{project_id}/runs",
    response_model=TestRunListResponse,
    summary="История запусков тестирования по проекту",
)
async def list_runs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> TestRunListResponse:
    runs = await list_runs_for_project(project_id, db)
    return TestRunListResponse(
        items=[TestRunOut.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.get(
    "/projects/{project_id}/completeness",
    summary="Анализ полноты тестирования (без запуска тестов)",
)
async def get_completeness(project_id: str) -> dict:
    """
    Быстрый статический анализ: какие исходные файлы не имеют
    соответствующего тест-файла. Не запускает тесты.
    """
    project_path = os.path.join(settings.storage_dir, project_id)
    if not os.path.isdir(project_path):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=f"Директория проекта не найдена: {project_path}",
        )
    report = analyze_completeness(project_path)
    return {
        "project_id": project_id,
        "source_count": report.source_count,
        "test_count": report.test_count,
        "untested_count": report.untested_count,
        "completeness_percent": report.completeness_percent,
        "untested_files": report.untested_files,
        "test_files": report.test_files,
        "source_files": report.source_files,
    }


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запуск тестирования",
)
async def remove_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_run(run_id, db)
