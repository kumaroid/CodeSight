from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import (
    SecurityScanDetail,
    SecurityScanListResponse,
    SecurityScanOut,
    StartSecurityScanRequest,
)
from .service import delete_scan, get_scan, list_scans_for_project, start_scan

router = APIRouter(prefix="/security", tags=["security"])


@router.post(
    "/scans",
    response_model=SecurityScanOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить проверку безопасности по OWASP Top 10",
)
async def create_scan(
    body: StartSecurityScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SecurityScanOut:
    """
    Принимает `project_id`, создаёт запись о сканировании (статус `pending`)
    и асинхронно запускает чекеры bandit + regex + pip-audit в фоне.
    Возвращает объект сканирования сразу — результаты появятся после завершения.
    """
    scan = await start_scan(body.project_id, db, background_tasks)
    return SecurityScanOut.model_validate(scan)


@router.get(
    "/scans/{scan_id}",
    response_model=SecurityScanDetail,
    summary="Получить результаты конкретного сканирования",
)
async def get_scan_by_id(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> SecurityScanDetail:
    """
    Возвращает сканирование вместе со всеми найденными уязвимостями (`findings`).
    Каждая находка включает OWASP-категорию, CWE, severity и местоположение в коде.
    Если сканирование ещё не завершено — `findings` будет пустым, а `status` — `running`.
    """
    scan = await get_scan(scan_id, db)
    return SecurityScanDetail.model_validate(scan)


@router.get(
    "/projects/{project_id}/scans",
    response_model=SecurityScanListResponse,
    summary="Список всех сканирований по проекту",
)
async def list_scans(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> SecurityScanListResponse:
    scans = await list_scans_for_project(project_id, db)
    return SecurityScanListResponse(
        items=[SecurityScanOut.model_validate(s) for s in scans],
        total=len(scans),
    )


@router.delete(
    "/scans/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить запись сканирования",
)
async def remove_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_scan(scan_id, db)
