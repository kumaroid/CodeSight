"""HTTP API DAST: чтение результатов прогонов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import DastRun
from .schemas import DastRunListResponse, DastRunOut

router = APIRouter(prefix="/dast", tags=["dast"])


@router.get(
    "/runs/{run_id}",
    response_model=DastRunOut,
    summary="Получить прогон DAST",
)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> DastRunOut:
    run = await db.get(DastRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DastRun {run_id!r} не найден",
        )
    return DastRunOut.model_validate(run)


@router.get(
    "/projects/{project_id}/runs",
    response_model=DastRunListResponse,
    summary="Список DAST-прогонов проекта",
)
async def list_runs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> DastRunListResponse:
    result = await db.execute(
        select(DastRun)
        .where(DastRun.project_id == project_id)
        .order_by(DastRun.created_at.desc())
    )
    runs = list(result.scalars().all())
    return DastRunListResponse(
        items=[DastRunOut.model_validate(r) for r in runs],
        total=len(runs),
    )
