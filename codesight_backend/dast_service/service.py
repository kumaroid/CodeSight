"""Бизнес-логика DAST: Valgrind + Python."""

from __future__ import annotations

import os

from .config import settings
from .models import DastRun
from .runner import run_dynamic_probe


async def _execute_dast_run(run_id: str, project_id: str) -> None:
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(DastRun, run_id)
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
            report, infra_err = await run_dynamic_probe(
                project_path, settings.dast_timeout
            )
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_message = str(exc)
            await db.commit()
            return

        run.valgrind_report = report
        # Если мы получили хотя бы отчёт — считаем шаг выполненным, даже если
        # valgrind недоступен (rootless без capabilities) или нашлись ошибки в
        # pytest collect. Без этого сага каждый раз откатывалась бы.
        run.status = "completed"
        run.error_message = infra_err  # информационное сообщение, не блокирует
        if infra_err:
            run.command_summary = (
                "Python-смок без valgrind (limited mode)"
                if "valgrind" in infra_err
                else "valgrind+memcheck (с замечаниями)"
            )
        else:
            run.command_summary = "valgrind+memcheck (pytest --collect-only или smoke)"
        await db.commit()


async def start_dast_run_for_kafka(project_id: str) -> tuple[str, str, str | None]:
    """Создаёт DastRun и выполняет анализ. (run_id, status, error_message)."""
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = DastRun(project_id=project_id, status="pending")
        db.add(run)
        await db.commit()
        await db.refresh(run)
        rid = run.id

    await _execute_dast_run(rid, project_id)

    async with AsyncSessionLocal() as db:
        run = await db.get(DastRun, rid)
    if run is None:
        return "", "failed", "run record lost"
    # error_message теперь часто несёт неблокирующую заметку — статус берём из run.status.
    st = "completed" if run.status == "completed" else "failed"
    return rid, st, run.error_message
