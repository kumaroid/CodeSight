"""Обёртки над инструментами статического анализа."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field


@dataclass
class RawIssue:
    tool: str
    severity: str  # error | warning | info
    file_path: str
    line: int | None
    column: int | None
    code: str | None
    message: str


async def _run(cmd: list[str], cwd: str) -> tuple[str, str, int]:
    """Запустить subprocess асинхронно и вернуть (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(errors="replace"), stderr.decode(errors="replace"), proc.returncode


# ---------------------------------------------------------------------------
# ruff
# ---------------------------------------------------------------------------

RUFF_SEVERITY: dict[str, str] = {
    "E": "error",
    "W": "warning",
    "F": "error",
    "B": "warning",
    "C": "warning",
    "I": "info",
    "N": "info",
    "UP": "info",
    "ANN": "info",
}


def _ruff_severity(code: str | None) -> str:
    if not code:
        return "warning"
    prefix = "".join(c for c in code if c.isalpha())
    return RUFF_SEVERITY.get(prefix, "warning")


async def run_ruff(project_path: str) -> list[RawIssue]:
    stdout, _, _ = await _run(
        ["ruff", "check", ".", "--output-format", "json", "--no-cache"],
        cwd=project_path,
    )
    issues: list[RawIssue] = []
    if not stdout.strip():
        return issues
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return issues

    for item in data:
        code = item.get("code")
        location = item.get("location") or {}
        issues.append(
            RawIssue(
                tool="ruff",
                severity=_ruff_severity(code),
                file_path=os.path.relpath(item.get("filename", ""), project_path),
                line=location.get("row"),
                column=location.get("column"),
                code=code,
                message=item.get("message", ""),
            )
        )
    return issues


# ---------------------------------------------------------------------------
# bandit
# ---------------------------------------------------------------------------

BANDIT_SEVERITY: dict[str, str] = {
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "info",
    "UNDEFINED": "info",
}


async def run_bandit(project_path: str) -> list[RawIssue]:
    stdout, _, _ = await _run(
        ["bandit", "-r", ".", "-f", "json", "-q"],
        cwd=project_path,
    )
    issues: list[RawIssue] = []
    if not stdout.strip():
        return issues
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return issues

    for item in data.get("results", []):
        sev = item.get("issue_severity", "UNDEFINED").upper()
        issues.append(
            RawIssue(
                tool="bandit",
                severity=BANDIT_SEVERITY.get(sev, "warning"),
                file_path=os.path.relpath(item.get("filename", ""), project_path),
                line=item.get("line_number"),
                column=None,
                code=item.get("test_id"),
                message=item.get("issue_text", ""),
            )
        )
    return issues


# ---------------------------------------------------------------------------
# mypy
# ---------------------------------------------------------------------------

async def run_mypy(project_path: str) -> list[RawIssue]:
    stdout, _, _ = await _run(
        [
            "mypy",
            ".",
            "--ignore-missing-imports",
            "--no-error-summary",
            "--output=json",
        ],
        cwd=project_path,
    )
    issues: list[RawIssue] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        severity_map = {"error": "error", "warning": "warning", "note": "info"}
        issues.append(
            RawIssue(
                tool="mypy",
                severity=severity_map.get(item.get("severity", "warning"), "warning"),
                file_path=os.path.relpath(item.get("file", ""), project_path),
                line=item.get("line"),
                column=item.get("column"),
                code=item.get("code"),
                message=item.get("message", ""),
            )
        )
    return issues


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

async def run_all(project_path: str) -> list[RawIssue]:
    """Запустить все анализаторы параллельно."""
    results = await asyncio.gather(
        run_ruff(project_path),
        run_bandit(project_path),
        run_mypy(project_path),
        return_exceptions=True,
    )
    issues: list[RawIssue] = []
    for result in results:
        if isinstance(result, list):
            issues.extend(result)
    return issues
