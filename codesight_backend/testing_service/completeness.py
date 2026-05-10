"""Анализ полноты тестирования: соотношение тест-файлов к исходным."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompletenessReport:
    """Отчёт о полноте покрытия тестами."""

    source_files: list[str]  # Python-файлы (не тесты)
    test_files: list[str]  # Файлы тестов
    untested_files: list[str]  # Исходники без соответствующего теста

    source_count: int
    test_count: int
    untested_count: int
    completeness_percent: float  # % исходников, у которых есть тест


def _collect_python_files(root: str) -> tuple[list[str], list[str]]:
    """
    Разделяет .py-файлы на исходники и тесты.
    Тест-файлами считаются файлы в директориях tests/test_*
    или с именем test_*.py / *_test.py.
    """
    source_files: list[str] = []
    test_files: list[str] = []

    skip_dirs = {
        "__pycache__",
        ".git",
        ".tox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".codesight_tmp",
        ".mypy_cache",
        ".ruff_cache",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        # Пропускаем скрытые и служебные директории
        dirnames[:] = [
            d for d in dirnames if d not in skip_dirs and not d.startswith(".")
        ]

        rel_dir = os.path.relpath(dirpath, root)
        is_test_dir = any(
            part in ("tests", "test") or part.startswith("test_")
            for part in Path(rel_dir).parts
        )

        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            if fname == "__init__.py" or fname == "conftest.py":
                continue

            rel_path = os.path.relpath(os.path.join(dirpath, fname), root)

            is_test_file = (
                is_test_dir or fname.startswith("test_") or fname.endswith("_test.py")
            )

            if is_test_file:
                test_files.append(rel_path)
            else:
                source_files.append(rel_path)

    return sorted(source_files), sorted(test_files)


def _guess_test_name(source_file: str) -> set[str]:
    """
    Для файла `pkg/module.py` возвращает возможные имена тест-файлов:
      test_module.py, module_test.py
    """
    stem = Path(source_file).stem
    return {f"test_{stem}.py", f"{stem}_test.py"}


def analyze_completeness(project_path: str) -> CompletenessReport:
    source_files, test_files = _collect_python_files(project_path)

    # Набор имён файлов тестов (без директорий, только basename)
    test_basenames = {os.path.basename(f) for f in test_files}

    untested: list[str] = []
    for src in source_files:
        expected = _guess_test_name(src)
        if not expected & test_basenames:
            untested.append(src)

    src_count = len(source_files)
    tested_count = src_count - len(untested)
    completeness = round(tested_count / src_count * 100, 2) if src_count else 100.0

    return CompletenessReport(
        source_files=source_files,
        test_files=test_files,
        untested_files=untested,
        source_count=src_count,
        test_count=len(test_files),
        untested_count=len(untested),
        completeness_percent=completeness,
    )
