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

import ast
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


def summary_from_persisted_run(run: ArchRun) -> dict | None:
    """Агрегаты avg_* и health-score из сохранённых метрик и рекомендаций.

    Поле ``summary`` не хранится в таблице ``arch_runs`` — при ``GET /runs/{id}``
    его нужно собрать заново (как после ``analyze_plantuml``), но с учётом всех
    записей в БД, включая AI-рекомендации, чтобы health-score совпадал с UI.
    """
    mlist = run.metrics
    if not mlist:
        return None
    n = len(mlist)
    avg_coupling = sum(m.coupling_score for m in mlist) / n
    avg_instability = sum(m.instability for m in mlist) / n
    # Cohesion может быть NULL для изолированных модулей — их пропускаем,
    # иначе среднее искусственно подтягивается к 1.0.
    cohesion_values = [m.cohesion_score for m in mlist if m.cohesion_score is not None]
    avg_cohesion = (
        round(sum(cohesion_values) / len(cohesion_values), 4)
        if cohesion_values
        else None
    )
    recs = run.recommendations or []
    critical_count = sum(1 for r in recs if r.severity == "critical")
    warning_count = sum(1 for r in recs if r.severity == "warning")
    health = max(0, 100 - critical_count * 20 - warning_count * 5)
    return {
        "components_count": n,
        "avg_coupling": round(avg_coupling, 4),
        "avg_cohesion": avg_cohesion,
        "avg_instability": round(avg_instability, 4),
        "critical_issues": critical_count,
        "warning_issues": warning_count,
        "architecture_health_score": health,
    }


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
    run_with = await get_run(run.id, db)
    persisted = summary_from_persisted_run(run_with)
    final_summary = persisted if persisted is not None else summary
    if persisted is not None and "ai_recommendations_count" in summary:
        final_summary = {
            **final_summary,
            "ai_recommendations_count": summary["ai_recommendations_count"],
        }
    return run_with, final_summary


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


def _find_effective_root(project_root: str) -> str:
    """Если в `project_root` ровно один не-blacklist подкаталог (типичный случай
    после `unzip` — в корне лежит `<projectname>-main/`), используем его как
    эффективный корень. Иначе возвращаем оригинальный путь.

    Полезно для AST-фолбэка, чтобы имена модулей не начинались
    c `plotva_ru_main.order_service.main`, а были просто `order_service.main`.
    """
    try:
        root = Path(project_root)
        children = list(root.iterdir())
    except OSError:
        return project_root
    dirs = [
        p
        for p in children
        if p.is_dir() and p.name not in _PKG_BLACKLIST and not p.name.startswith(".")
    ]
    # Скрытые файлы (`.coverage`, `.env` от прошлых прогонов) не считаются:
    # иначе в проектах после `unzip` мы не спускаемся в единственный поддиректорий.
    files = [p for p in children if p.is_file() and not p.name.startswith(".")]
    if len(dirs) == 1 and not files:
        return str(dirs[0])
    return project_root


def _normalize_module_segment(name: str) -> str | None:
    """Нормализует сегмент пути в допустимый идентификатор Python-модуля."""
    np = name.replace("-", "_").replace(".", "_")
    if not np.isidentifier():
        return None
    return np


def _module_namespace(analysis_root: Path) -> str:
    """Короткий префикс для модулей из отдельного дерева (микросервис, пакет)."""
    seg = _normalize_module_segment(analysis_root.name)
    return seg or ""


def _qualify_module(mod: str, namespace: str) -> str:
    if not namespace:
        return mod
    return f"{namespace}.{mod}" if mod else namespace


def _discover_ast_roots(project_root: str) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path.resolve())
        if key in seen:
            return
        seen.add(key)
        roots.append(path.resolve())

    packages = _find_python_packages(project_root)
    for parent in packages:
        add(Path(parent))

    # Микросервисы вроде display-service: есть .py, но нет app/__init__.py.
    package_parents = {str(Path(p).resolve()) for p in packages}
    for parent, pkgs in packages.items():
        parent_path = Path(parent)
        parent_pkgs = set(pkgs)
        try:
            children = list(parent_path.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir():
                continue
            if child.name in _PKG_BLACKLIST or child.name.startswith("."):
                continue
            if child.name in parent_pkgs:
                continue
            child_key = str(child.resolve())
            if child_key in package_parents:
                continue
            py_files = [
                p
                for p in child.rglob("*.py")
                if p.name != "setup.py"
                and not any(part in _PKG_BLACKLIST for part in p.parts)
            ]
            if len(py_files) >= 2:
                add(child)

        # Сервисы внутри src-layout: `backend/src/display-service/` без корневого пакета.
        for pkg in pkgs:
            pkg_dir = parent_path / pkg
            if not pkg_dir.is_dir():
                continue
            try:
                pkg_children = list(pkg_dir.iterdir())
            except OSError:
                continue
            for child in pkg_children:
                if not child.is_dir():
                    continue
                if child.name in _PKG_BLACKLIST or child.name.startswith("."):
                    continue
                # Внутри src-layout отдельными корнями считаем только «*-service»
                # каталоги (микросервисы). Пакеты вроде `animeshki/` остаются
                # частью родительского дерева `backend/src`.
                if not child.name.endswith("-service"):
                    continue
                child_key = str(child.resolve())
                if child_key in package_parents or child_key in seen:
                    continue
                py_files = [
                    p
                    for p in child.rglob("*.py")
                    if p.name != "setup.py"
                    and not any(part in _PKG_BLACKLIST for part in p.parts)
                ]
                if len(py_files) >= 2:
                    add(child)

    if not roots:
        add(Path(_find_effective_root(project_root)).resolve())
    return roots


def _collect_ast_graph(
    analysis_root: Path,
    namespace: str,
    excluded_prefixes: tuple[str, ...] = (),
) -> tuple[dict[Path, str], set[tuple[str, str]]]:
    """Строит граф import-зависимостей для одного корня анализа."""
    py_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(analysis_root):
        current = str(Path(dirpath).resolve())
        if any(
            current == ex or current.startswith(ex + os.sep) for ex in excluded_prefixes
        ):
            dirnames.clear()
            continue
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _PKG_BLACKLIST
            and not d.startswith(".")
            and not any(
                (current + os.sep + d) == ex
                or (current + os.sep + d).startswith(ex + os.sep)
                for ex in excluded_prefixes
            )
        ]
        for fname in filenames:
            if fname.endswith(".py") and fname != "setup.py":
                py_files.append(Path(dirpath) / fname)

    file_to_mod: dict[Path, str] = {}
    for path in py_files:
        mod = _module_for_path(path, analysis_root)
        if mod:
            file_to_mod[path] = _qualify_module(mod, namespace)

    known: set[str] = set(file_to_mod.values())

    def resolve(target: str, source_mod: str) -> str | None:
        """Сводит import-target к известному модулю в текущем дереве."""
        if not target:
            return None
        if target in known:
            return target
        parent_pkg = ".".join(source_mod.split(".")[:-1])
        if parent_pkg:
            sibling = f"{parent_pkg}.{target}"
            if sibling in known:
                return sibling
        parts = target.split(".")
        for cut in range(len(parts) - 1, 0, -1):
            cand = ".".join(parts[:cut])
            if cand in known:
                return cand
        prefix = target + "."
        for k in known:
            if k.startswith(prefix):
                return target
        return None

    edges: set[tuple[str, str]] = set()
    for path, mod in file_to_mod.items():
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, ValueError, OSError):
            continue
        pkg_parts = mod.split(".")[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = resolve(alias.name, mod)
                    if target and target != mod:
                        edges.add((mod, target))
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    base = pkg_parts[: max(0, len(pkg_parts) - (node.level - 1))]
                    parts = base + ([node.module] if node.module else [])
                    if not parts:
                        continue
                    target_name = ".".join(parts)
                elif node.module:
                    target_name = node.module
                else:
                    continue
                target = resolve(target_name, mod)
                if target and target != mod:
                    edges.add((mod, target))

    return file_to_mod, edges


def _module_for_path(path: Path, project_root: Path) -> str | None:
    """Имя Python-модуля по пути файла относительно `project_root`.

    Поддерживает src-layout (`src/plotva/foo.py` → `plotva.foo`) и
    namespace-packages (PEP 420, без `__init__.py`). Сегменты с дефисами
    нормализуются: `order-service/main.py` → `order_service.main`.
    """
    try:
        rel = path.resolve().relative_to(project_root.resolve())
    except (ValueError, OSError):
        return None
    parts = list(rel.parts)
    if not parts:
        return None
    if parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    if not parts:
        return None
    norm: list[str] = []
    for p in parts:
        if not p:
            continue
        np = _normalize_module_segment(p)
        if np is None:
            return None
        norm.append(np)
    if not norm:
        return None
    return ".".join(norm)


def _generate_plantuml_via_ast(
    project_root: str,
) -> tuple[str | None, str | None]:
    """Альтернативный анализатор: строит PlantUML напрямую через AST.

    Покрывает кейсы, в которых arch-blueprint (grimp) бесполезен:

    - PEP 420 namespace-packages — каталоги c `.py` файлами, но без `__init__.py`
      (типичная структура микросервисов с `pyproject.toml`).
    - Несколько независимых сервисов в одном дереве без общего корневого пакета.
    - Flat-layout: модули в корне проекта и «плоские» импорты (`from settings import …`).

    AST-проход дешевле и устойчивее grimp'а: он не падает на синтаксических
    ошибках отдельных файлов и не требует, чтобы проект пользователя
    был импортируемым в окружении сервиса.

    Возвращает (plantuml_text, warning). Текст — `None`, если в проекте
    меньше двух Python-модулей.
    """
    roots = _discover_ast_roots(project_root)
    use_namespace = len(roots) > 1
    root_strs = [str(r.resolve()) for r in roots]

    all_mods: dict[Path, str] = {}
    all_edges: set[tuple[str, str]] = set()
    for analysis_root in roots:
        namespace = _module_namespace(analysis_root) if use_namespace else ""
        excluded = tuple(
            other
            for other in root_strs
            if other != str(analysis_root.resolve())
            and other.startswith(str(analysis_root.resolve()) + os.sep)
        )
        file_to_mod, edges = _collect_ast_graph(analysis_root, namespace, excluded)
        all_mods.update(file_to_mod)
        all_edges.update(edges)

    if len(all_mods) < 2:
        return None, "AST-fallback: <2 .py файлов"

    nodes = set(all_mods.values())
    for _, dst in all_edges:
        nodes.add(dst)

    if len(nodes) < 2:
        return None, "AST-fallback: получилось <2 узлов"

    out = ["@startuml"]
    for n in sorted(nodes):
        out.append(f"class {n} <<(M, #2ECC71)>>")
    for src, dst in sorted(all_edges):
        out.append(f"{src} ---> {dst}")
    out.append("@enduml")
    return "\n".join(out), None


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
        # trust_env=False — archer находится во внутренней сети Docker,
        # системный SOCKS-прокси (если задан на хосте) внутри контейнера
        # недоступен и только мешает.
        async with httpx.AsyncClient(
            timeout=settings.archer_timeout_seconds,
            trust_env=False,
        ) as client:
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
        # Запускаем оба анализатора и склеиваем их вывод:
        # - arch-blueprint (grimp) точнее на пакетах с `__init__.py`;
        # - AST-фолбэк покрывает namespace-packages (PEP 420) и flat-layout.
        # Дубликаты по имени модуля схлопнет `analyze_plantuml`.
        bp_text, bp_warn = await _generate_plantuml_with_arch_blueprint(base)
        ast_text, ast_warn = _generate_plantuml_via_ast(base)
        sections: list[str] = []
        if bp_text:
            sections.append(_strip_uml_envelope(bp_text))
        if ast_text:
            sections.append(_strip_uml_envelope(ast_text))
        if sections:
            text = "@startuml\n" + "\n\n".join(sections) + "\n@enduml"
        warnings = [w for w in (bp_warn, ast_warn) if w]
        blueprint_warning = "; ".join(warnings) if warnings else None

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
