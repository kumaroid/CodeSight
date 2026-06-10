"""Бизнес-логика DAST: probe-based динамический анализ."""

from __future__ import annotations

import cProfile
import io
import logging
import os
import pstats
from typing import Any

from .config import settings
from .models import DastRun
from .runner import run_dynamic_probes

logger = logging.getLogger(__name__)

# Postgres (через asyncpg) отклоняет U+0000 в TEXT / JSON — «unsupported Unicode escape».
_NUL = "\x00"


def _strip_nul(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace(_NUL, "") if _NUL in text else text


def _strip_nul_json(value: Any) -> Any:
    """Рекурсивно убирает NUL из строк в dict/list/tuple для JSONB."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.replace(_NUL, "") if _NUL in value else value
    if isinstance(value, dict):
        return {k: _strip_nul_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_nul_json(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_strip_nul_json(v) for v in value)
    return value


def _resolve_project_root(project_path: str) -> str:
    """
    Возвращает «эффективный» корень проекта.

    Старые проекты, загруженные через ``loader_service`` ДО фикса
    флаттенинга, лежат в виде ``<storage>/<project_id>/<repo>-<branch>/...``
    (GitHub-овый архив `archive/refs/heads/<branch>.zip` всегда содержит
    обёртывающую папку). В таком случае probes, которые ищут манифесты
    в корне (``pip_check`` → ``pyproject.toml``/``requirements*.txt``),
    ошибочно репортят «не найдено».

    Эвристика: если на верхнем уровне ровно один элемент и это директория,
    считаем её настоящим корнем. Для новых, плоско распакованных проектов
    эта функция — ноп.
    """
    try:
        entries = os.listdir(project_path)
    except OSError:
        return project_path
    if len(entries) != 1:
        return project_path
    only = os.path.join(project_path, entries[0])
    if os.path.isdir(only):
        return only
    return project_path


def _mode_to_summary(mode: str, aggregate: dict) -> str:
    """Краткое описание режима для колонки command_summary (UI)."""
    by_status = aggregate.get("probes_by_status", {})
    ran = sum(v for k, v in by_status.items() if k != "skipped")
    skipped = by_status.get("skipped", 0)
    if mode == "native+memcheck":
        head = "valgrind+memcheck + python probes"
    elif mode == "pure-python":
        head = "python probes (без memcheck, нет C-расширений)"
    else:
        head = mode or "limited"
    return f"{head} · {ran} probes выполнено, {skipped} пропущено"


def _log_profile_stats(profiler: cProfile.Profile, top_n: int = 20) -> None:
    """Выводит топ-N функций по совокупному времени (cumulative) в лог."""
    stream = io.StringIO()
    ps = pstats.Stats(profiler, stream=stream)
    ps.strip_dirs()
    ps.sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(top_n)
    logger.info("DAST cProfile report (top %d by cumtime):\n%s", top_n, stream.getvalue())


async def _execute_dast_run(run_id: str, project_id: str) -> None:
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(DastRun, run_id)
        if run is None:
            return

        project_path = os.path.join(settings.storage_dir, project_id)
        if not os.path.isdir(project_path):
            run.status = "failed"
            run.error_message = _strip_nul(
                f"Директория проекта не найдена: {project_path}"
            )
            await db.commit()
            return

        # Страховка для legacy-проектов, у которых остался GitHub-овый
        # обёртывающий каталог (`<repo>-<branch>/...`): пробуем спуститься
        # на уровень ниже, если на верхнем лежит ровно одна директория.
        effective_path = _resolve_project_root(project_path)
        if effective_path != project_path:
            logger.info(
                "DAST: использую эффективный корень %s (вместо %s)",
                effective_path,
                project_path,
            )

        run.status = "running"
        await db.commit()

        profiler = cProfile.Profile()
        try:
            profiler.enable()
            report = await run_dynamic_probes(effective_path, settings.dast_timeout)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка DAST runner для project=%s", project_id)
            run.status = "failed"
            run.error_message = _strip_nul(str(exc))
            await db.commit()
            return
        finally:
            profiler.disable()
            _log_profile_stats(profiler)

        aggregate = _strip_nul_json(report.aggregate)
        by_sev = aggregate.get("findings_by_severity", {})

        run.mode = _strip_nul(report.mode)
        run.probes = _strip_nul_json(report.probes_as_dicts())
        run.aggregate = aggregate
        run.findings_total = int(aggregate.get("findings_total", 0))
        run.findings_errors = int(by_sev.get("error", 0))
        run.findings_warnings = int(by_sev.get("warning", 0))
        raw_log = _strip_nul(report.raw_log)
        run.raw_log = raw_log
        # Алиас для обратной совместимости со старым клиентом/UI.
        run.valgrind_report = raw_log
        run.command_summary = _strip_nul(_mode_to_summary(report.mode, aggregate))

        # Шаг считается выполненным, если у нас вообще удалось собрать
        # хотя бы один probe-результат. Конкретные ошибки внутри probes —
        # это findings, а не «инфраструктурный сбой саги».
        has_errors = run.findings_errors > 0
        run.status = "completed"
        run.error_message = _strip_nul(
            f"DAST завершился с {run.findings_errors} ошибками и "
            f"{run.findings_warnings} предупреждениями (см. отчёт)."
            if has_errors
            else None
        )

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
    st = "completed" if run.status == "completed" else "failed"
    return rid, st, run.error_message
