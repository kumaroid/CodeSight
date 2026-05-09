"""Запуск pytest + pytest-cov и парсинг результатов."""

from __future__ import annotations

import asyncio
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Данные-транспорты
# ---------------------------------------------------------------------------


@dataclass
class RawFileCoverage:
    file_path: str
    lines_total: int
    lines_covered: int
    lines_missing: int
    coverage_percent: float
    missing_lines: list[int] = field(default_factory=list)


@dataclass
class RawTestResult:
    node_id: str
    outcome: str  # passed | failed | error | skipped
    duration_seconds: float | None
    longrepr: str | None


@dataclass
class RawRunResult:
    # Итоговые метрики покрытия
    coverage_percent: float
    lines_total: int
    lines_covered: int
    lines_missing: int
    branches_total: int
    branches_covered: int
    branch_coverage_percent: float

    # Итоговые метрики тестов
    tests_total: int
    tests_passed: int
    tests_failed: int
    tests_error: int
    tests_skipped: int
    duration_seconds: float

    # Детали
    file_coverages: list[RawFileCoverage] = field(default_factory=list)
    test_results: list[RawTestResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run(
    cmd: list[str], cwd: str, timeout: int
) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"Таймаут выполнения команды {' '.join(cmd)} ({timeout}s)")
    return stdout.decode(errors="replace"), stderr.decode(errors="replace"), proc.returncode


def _safe_div(a: int, b: int) -> float:
    return round(a / b * 100, 2) if b else 0.0


# ---------------------------------------------------------------------------
# Парсинг coverage.xml (Cobertura format)
# ---------------------------------------------------------------------------


def _parse_coverage_xml(xml_path: str, project_path: str) -> tuple[
    float, int, int, int, int, int, float, list[RawFileCoverage]
]:
    """
    Возвращает:
      (coverage_pct, lines_total, lines_covered, lines_missing,
       branches_total, branches_covered, branch_pct, file_coverages)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    line_rate = float(root.attrib.get("line-rate", 0))
    branch_rate = float(root.attrib.get("branch-rate", 0))
    lines_valid = int(root.attrib.get("lines-valid", 0))
    lines_covered_total = int(root.attrib.get("lines-covered", 0))
    branches_valid = int(root.attrib.get("branches-valid", 0) or 0)
    branches_covered_total = int(root.attrib.get("branches-covered", 0) or 0)

    coverage_pct = round(line_rate * 100, 2)
    branch_pct = round(branch_rate * 100, 2)
    lines_missing_total = lines_valid - lines_covered_total

    file_coverages: list[RawFileCoverage] = []
    for cls in root.iter("class"):
        fname = cls.attrib.get("filename", "")
        rel_path = os.path.relpath(fname, project_path) if os.path.isabs(fname) else fname

        lines = cls.findall("lines/line")
        f_total = len(lines)
        f_covered = sum(1 for l in lines if int(l.attrib.get("hits", 0)) > 0)
        f_missing_nums = [
            int(l.attrib.get("number", 0))
            for l in lines
            if int(l.attrib.get("hits", 0)) == 0
        ]

        file_coverages.append(
            RawFileCoverage(
                file_path=rel_path,
                lines_total=f_total,
                lines_covered=f_covered,
                lines_missing=f_total - f_covered,
                coverage_percent=_safe_div(f_covered, f_total),
                missing_lines=f_missing_nums,
            )
        )

    return (
        coverage_pct,
        lines_valid,
        lines_covered_total,
        lines_missing_total,
        branches_valid,
        branches_covered_total,
        branch_pct,
        file_coverages,
    )


# ---------------------------------------------------------------------------
# Парсинг junit.xml
# ---------------------------------------------------------------------------


def _parse_junit_xml(xml_path: str) -> tuple[int, int, int, int, int, float, list[RawTestResult]]:
    """
    Возвращает:
      (total, passed, failed, errors, skipped, duration, test_results)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # <testsuites> или <testsuite> на верхнем уровне
    suites = root.findall("testsuite") or [root]
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    else:
        suites = [root]

    total = failed = errors = skipped = 0
    duration = 0.0
    test_results: list[RawTestResult] = []

    for suite in suites:
        total += int(suite.attrib.get("tests", 0))
        failed += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
        duration += float(suite.attrib.get("time", 0) or 0)

        for tc in suite.findall("testcase"):
            classname = tc.attrib.get("classname", "")
            name = tc.attrib.get("name", "")
            node_id = f"{classname}::{name}" if classname else name
            t = float(tc.attrib.get("time", 0) or 0)

            failure = tc.find("failure")
            error = tc.find("error")
            skip = tc.find("skipped")

            if failure is not None:
                outcome = "failed"
                longrepr = failure.attrib.get("message") or failure.text or ""
            elif error is not None:
                outcome = "error"
                longrepr = error.attrib.get("message") or error.text or ""
            elif skip is not None:
                outcome = "skipped"
                longrepr = skip.attrib.get("message") or skip.text or ""
            else:
                outcome = "passed"
                longrepr = None

            test_results.append(
                RawTestResult(
                    node_id=node_id,
                    outcome=outcome,
                    duration_seconds=t,
                    longrepr=longrepr,
                )
            )

    passed = total - failed - errors - skipped
    return total, passed, failed, errors, skipped, round(duration, 3), test_results


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


async def run_tests(project_path: str, timeout: int = 120) -> RawRunResult:
    """
    Запускает pytest с coverage в директории проекта.
    Возвращает RawRunResult с полными метриками.
    """
    tmp_dir = Path(project_path) / ".codesight_tmp"
    tmp_dir.mkdir(exist_ok=True)

    coverage_xml = str(tmp_dir / "coverage.xml")
    junit_xml = str(tmp_dir / "junit.xml")

    cmd = [
        "python", "-m", "pytest",
        "--tb=short",
        "--quiet",
        f"--junitxml={junit_xml}",
        f"--cov={project_path}",
        "--cov-branch",
        f"--cov-report=xml:{coverage_xml}",
        "--cov-report=term-missing:skip-covered",
        "--no-header",
    ]

    await _run(cmd, cwd=project_path, timeout=timeout)

    # --- Парсим coverage ---
    if os.path.exists(coverage_xml):
        (
            cov_pct, lines_total, lines_covered, lines_missing,
            branches_total, branches_covered, branch_pct,
            file_coverages,
        ) = _parse_coverage_xml(coverage_xml, project_path)
    else:
        cov_pct = lines_total = lines_covered = lines_missing = 0
        branches_total = branches_covered = 0
        branch_pct = 0.0
        file_coverages = []

    # --- Парсим junit ---
    if os.path.exists(junit_xml):
        (
            tests_total, tests_passed, tests_failed, tests_error,
            tests_skipped, duration, test_results,
        ) = _parse_junit_xml(junit_xml)
    else:
        tests_total = tests_passed = tests_failed = tests_error = tests_skipped = 0
        duration = 0.0
        test_results = []

    # Очищаем временные файлы
    for f in [coverage_xml, junit_xml]:
        try:
            os.remove(f)
        except OSError:
            pass

    return RawRunResult(
        coverage_percent=cov_pct,
        lines_total=lines_total,
        lines_covered=lines_covered,
        lines_missing=lines_missing,
        branches_total=branches_total,
        branches_covered=branches_covered,
        branch_coverage_percent=branch_pct,
        tests_total=tests_total,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_error=tests_error,
        tests_skipped=tests_skipped,
        duration_seconds=duration,
        file_coverages=file_coverages,
        test_results=test_results,
    )
