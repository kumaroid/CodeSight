"""Бизнес-логика сервиса архитектурного анализа.

Поток для шага саги (`run_arch_analysis_from_workspace`):

1. Загружаем PlantUML из проекта:
   - если в проекте лежит `*.puml` (приоритет — `diagram.puml`,
     `architecture.puml`, `docs/diagram.puml`) — используем его как есть;
   - иначе запускаем `arch-blueprint` на найденных Python-пакетах и
     получаем PlantUML с графом импортов модулей.
2. Парсим PlantUML, считаем Coupling/Cohesion/Instability.
3. Генерируем rule-based рекомендации.
4. Best-effort обращаемся в `archer` (LLM-агент). Если он недоступен —
   шаг считается успешным, остаются только rule-based рекомендации.
5. Всё сохраняем в БД и возвращаем `run_id`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .analyzer import analyze_plantuml
from .models import ArchRecommendation, ArchRun, ComponentMetric

logger = logging.getLogger(__name__)

# Каталоги, которые игнорируем при поиске Python-пакетов
_PKG_BLACKLIST = {
    "tests",
    "test",
    "docs",
    "doc",
    "examples",
    "example",
    "venv",
    ".venv",
    "env",
    "build",
    "dist",
    "node_modules",
    "__pycache__",
    "site-packages",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".git",
}


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

    # Best-effort обогащение AI-рекомендациями
    ai_recs = await _fetch_ai_recommendations(
        project_id=project_id,
        metrics=metrics,
        rule_recs=recommendations,
        summary=summary,
    )
    if ai_recs:
        summary = {**summary, "ai_recommendations_count": len(ai_recs)}
        for ai in ai_recs:
            db.add(
                ArchRecommendation(
                    run_id=run.id,
                    severity=ai["severity"],
                    component=ai.get("component"),
                    rule=ai["rule"],
                    message=ai["message"],
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


# --------------------------------------------------------------------------- #
# Поиск/генерация PlantUML по проекту
# --------------------------------------------------------------------------- #


def _load_first_plantuml(project_root: str) -> str | None:
    """Ищет PlantUML: сначала приоритетные имена, затем любой .puml."""
    preferred = (
        "diagram.puml",
        "architecture.puml",
        os.path.join("docs", "diagram.puml"),
        os.path.join("docs", "architecture.puml"),
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


def _find_python_packages(root: str, max_depth: int = 4) -> dict[str, list[str]]:
    """Ищет «корневые» Python-пакеты в проекте.

    Возвращает словарь `{parent_dir: [pkg_name, ...]}`. `parent_dir` — это
    каталог, который надо передать в `arch-blueprint` как `project_dir`,
    а `pkg_name` — топ-левел пакеты, найденные внутри него.

    Пакет считается «корневым», если он сам содержит `__init__.py`,
    а его родитель — НЕ содержит (т.е. это самый внешний пакет в цепочке).
    """
    by_parent: dict[str, list[str]] = {}
    seen: set[str] = set()
    root_path = Path(root).resolve()

    for dirpath, dirnames, filenames in os.walk(root_path):
        # фильтруем мусор и слишком глубокие пути
        rel = Path(dirpath).resolve().relative_to(root_path).parts
        depth = len(rel)
        if depth > max_depth:
            dirnames.clear()
            continue
        # in-place чтобы os.walk не спускался в blacklisted директории
        dirnames[:] = [
            d for d in dirnames if d not in _PKG_BLACKLIST and not d.startswith(".")
        ]

        if "__init__.py" not in filenames:
            continue
        pkg_name = Path(dirpath).name
        if (
            pkg_name in _PKG_BLACKLIST
            or pkg_name.startswith(".")
            or not pkg_name.isidentifier()
        ):
            continue
        parent = str(Path(dirpath).parent)
        # пропускаем, если родитель сам пакет — это вложенный модуль
        if os.path.isfile(os.path.join(parent, "__init__.py")):
            continue
        key = f"{parent}|{pkg_name}"
        if key in seen:
            continue
        seen.add(key)
        by_parent.setdefault(parent, []).append(pkg_name)

    return by_parent


async def _run_arch_blueprint(
    project_dir: str,
    modules: list[str],
    timeout: float,
) -> tuple[str, str]:
    """Запускает arch-blueprint и возвращает (stdout, stderr).

    Используем подпроцесс, чтобы изолировать падения grimp (синтаксические
    ошибки в проекте пользователя, циклические импорты, отсутствующие зависимости).
    """
    cmd = [
        "python",
        "-m",
        "arch_blueprint",
        project_dir,
        "--format",
        "puml",
        "-m",
        *modules,
    ]
    logger.info("Запускаем arch-blueprint: %s (cwd=%s)", " ".join(cmd), project_dir)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=project_dir,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return "", f"arch-blueprint timeout after {timeout}s"
    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        logger.warning(
            "arch-blueprint завершился с кодом %s: %s", proc.returncode, stderr
        )
    return stdout, stderr


def _strip_uml_envelope(text: str) -> str:
    """Убирает @startuml/@enduml, чтобы можно было сшить несколько диаграмм."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("@startuml") or stripped.startswith("@enduml"):
            continue
        lines.append(line)
    return "\n".join(lines)


async def _generate_plantuml_with_arch_blueprint(
    project_root: str,
) -> tuple[str | None, str | None]:
    """Гoтовит PlantUML через arch-blueprint.

    Возвращает (plantuml_text, warning). Если что-то пошло не так — текст
    может быть None, а warning описывает причину.
    """
    if shutil.which("python") is None:
        return None, "python отсутствует в PATH контейнера"

    packages = _find_python_packages(project_root)
    if not packages:
        return None, "В проекте не найдено Python-пакетов (директорий с __init__.py)"

    from .config import settings

    sections: list[str] = []
    warnings: list[str] = []
    for parent, pkgs in packages.items():
        modules = [f"{p}.**" for p in pkgs] + [f"{p}.*" for p in pkgs] + list(pkgs)
        # ↑ паттерны: pkg.** ловит всю иерархию, pkg.* — прямых детей, pkg — сам корень
        stdout, stderr = await _run_arch_blueprint(
            project_dir=parent,
            modules=modules,
            timeout=settings.arch_blueprint_timeout_seconds,
        )
        if stdout.strip():
            sections.append(_strip_uml_envelope(stdout))
        if stderr.strip() and "Traceback" in stderr:
            warnings.append(
                f"{','.join(pkgs)}: {stderr.strip().splitlines()[-1][:200]}"
            )

    if not sections:
        return None, "; ".join(warnings) or "arch-blueprint не вернул PlantUML"

    body = "\n\n".join(sections)
    return f"@startuml\n{body}\n@enduml", "; ".join(warnings) if warnings else None


# --------------------------------------------------------------------------- #
# Archer (LLM-агент)
# --------------------------------------------------------------------------- #


async def _fetch_ai_recommendations(
    project_id: str,
    metrics: list,
    rule_recs: list,
    summary: dict,
) -> list[dict]:
    """Best-effort вызов archer.

    Возвращает список рекомендаций в формате
    `{severity, component, rule, message}`. При любой проблеме (archer
    отключён, недоступен, отдал не-JSON) возвращаем пустой список и
    логируем — пайплайн не должен падать из-за LLM.
    """
    from .config import settings

    if not settings.archer_url:
        return []

    payload = {
        "project_id": project_id,
        "summary": summary,
        "metrics": [
            {
                "component": m.component,
                "ca": m.ca,
                "ce": m.ce,
                "instability": m.instability,
                "coupling_score": m.coupling_score,
                "cohesion_score": m.cohesion_score,
            }
            for m in metrics
        ],
        "rule_recommendations": [
            {
                "severity": r.severity,
                "component": r.component,
                "rule": r.rule,
                "message": r.message,
            }
            for r in rule_recs
        ],
    }

    url = settings.archer_url.rstrip("/") + "/analyze-metrics"
    try:
        async with httpx.AsyncClient(timeout=settings.archer_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Archer недоступен, пропускаем AI-рекомендации: %s", exc)
        return []

    items = data.get("recommendations") or []
    normalized: list[dict] = []
    for item in items:
        msg = item.get("message") or item.get("recommendation") or ""
        if not msg:
            continue
        normalized.append(
            {
                "severity": item.get("severity") or item.get("priority") or "info",
                "component": item.get("component"),
                "rule": item.get("rule") or "AI_HINT",
                "message": msg[:2000],  # защита от слишком длинных ответов
            }
        )
    return normalized


# --------------------------------------------------------------------------- #
# Точка входа из Kafka-обработчика
# --------------------------------------------------------------------------- #


async def run_arch_analysis_from_workspace(
    project_id: str,
) -> tuple[str, str, str | None]:
    """
    Запуск из Kafka: читает/генерирует PlantUML и сохраняет результаты.
    Возвращает (run_id, status, error_message).
    """
    from .config import settings
    from .database import AsyncSessionLocal

    base = os.path.join(settings.project_storage_dir, project_id)
    if not os.path.isdir(base):
        return "", "failed", f"Директория проекта не найдена: {base}"

    text = _load_first_plantuml(base)
    blueprint_warning: str | None = None
    if not text:
        text, blueprint_warning = await _generate_plantuml_with_arch_blueprint(base)

    async with AsyncSessionLocal() as db:
        if not text:
            run = ArchRun(
                project_id=project_id,
                status="completed",
                error_message=(
                    blueprint_warning
                    or "Не удалось сгенерировать PlantUML; шаг пропущен без метрик."
                ),
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
            # Если есть предупреждение от arch-blueprint (частичный успех) —
            # прокидываем его в error_message без изменения статуса.
            if blueprint_warning:
                run.error_message = blueprint_warning
                async with AsyncSessionLocal() as db3:
                    obj = await db3.get(ArchRun, run.id)
                    if obj is not None:
                        obj.error_message = blueprint_warning
                        await db3.commit()
            return run.id, run.status, run.error_message
