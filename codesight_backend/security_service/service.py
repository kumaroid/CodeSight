"""Бизнес-логика сервиса проверки безопасности."""

from __future__ import annotations

import os

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .checkers import run_all
from .config import settings
from .models import SecurityFinding, SecurityScan


async def start_scan(
    project_id: str,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> SecurityScan:
    """Создать запись о сканировании и поставить задачу в фон."""
    scan = SecurityScan(project_id=project_id, status="pending")
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    background_tasks.add_task(_execute_scan, scan.id, project_id)
    return scan


async def _execute_scan(scan_id: str, project_id: str) -> None:
    """Фоновая задача: запустить чекеры и сохранить результаты."""
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        scan = await db.get(SecurityScan, scan_id)
        if scan is None:
            return

        project_path = os.path.join(settings.storage_dir, project_id)
        if not os.path.isdir(project_path):
            scan.status = "failed"
            scan.error_message = f"Директория проекта не найдена: {project_path}"
            await db.commit()
            return

        scan.status = "running"
        await db.commit()

        try:
            raw_findings = await run_all(project_path)
        except Exception as exc:  # noqa: BLE001
            scan.status = "failed"
            scan.error_message = str(exc)
            await db.commit()
            return

        for raw in raw_findings:
            finding = SecurityFinding(
                scan_id=scan_id,
                owasp_category=raw.owasp_category,
                owasp_title=raw.owasp_title,
                checker=raw.checker,
                severity=raw.severity,
                file_path=raw.file_path,
                line=raw.line,
                column=raw.column,
                code=raw.code,
                message=raw.message,
                cwe=raw.cwe,
            )
            db.add(finding)

        scan.status = "completed"
        await db.commit()


async def get_scan(
    scan_id: str,
    db: AsyncSession,
) -> SecurityScan:
    result = await db.execute(
        select(SecurityScan)
        .options(selectinload(SecurityScan.findings))
        .where(SecurityScan.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityScan {scan_id!r} не найден",
        )
    return scan


async def list_scans_for_project(
    project_id: str,
    db: AsyncSession,
) -> list[SecurityScan]:
    result = await db.execute(
        select(SecurityScan)
        .where(SecurityScan.project_id == project_id)
        .order_by(SecurityScan.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_scan(
    scan_id: str,
    db: AsyncSession,
) -> None:
    scan = await db.get(SecurityScan, scan_id)
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SecurityScan {scan_id!r} не найден",
        )
    await db.delete(scan)
    await db.commit()
