"""HTTP-роутер оркестратора."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import SagaState
from .saga import start_saga
from .schemas import SagaResponse, StartAnalysisRequest

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


@router.post(
    "/sagas",
    response_model=SagaResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить анализ (Saga)",
)
async def create_saga(
    body: StartAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> SagaResponse:
    """
    Создаёт новую сагу и запускает распределённый анализ проекта.

    - **project_id** — идентификатор проекта (уже загруженного через loader_service).
    - **steps** — список видов анализа: `analysis`, `security`, `arch`, `testing`.
      По умолчанию запускаются все четыре.
    """
    try:
        steps = body.validated_steps()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saga = SagaState(
        project_id=body.project_id,
        requested_steps=json.dumps(steps),
        steps_status=json.dumps({s: "pending" for s in steps}),
        steps_run_ids=json.dumps({}),
        status="pending",
    )
    db.add(saga)
    await db.commit()
    await db.refresh(saga)

    # Запускаем сагу (отправляем команды в Kafka)
    await start_saga(saga)

    return SagaResponse.from_orm(saga)


@router.get(
    "/sagas/{saga_id}",
    response_model=SagaResponse,
    summary="Получить состояние саги",
)
async def get_saga(
    saga_id: str,
    db: AsyncSession = Depends(get_db),
) -> SagaResponse:
    saga = await db.get(SagaState, saga_id)
    if saga is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Сага {saga_id!r} не найдена",
        )
    return SagaResponse.from_orm(saga)


@router.get(
    "/sagas",
    response_model=list[SagaResponse],
    summary="Список саг для проекта",
)
async def list_sagas(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SagaResponse]:
    result = await db.execute(
        select(SagaState)
        .where(SagaState.project_id == project_id)
        .order_by(SagaState.created_at.desc())
    )
    return [SagaResponse.from_orm(s) for s in result.scalars().all()]
