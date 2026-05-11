"""Запуск Valgrind вокруг лёгкой динамической проверки Python в каталоге проекта."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile


def _truncate(text: str, max_len: int = 120_000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 80] + "\n\n… [truncated] …\n"


async def _run_valgrind_subprocess(
    *,
    cwd: str,
    timeout_sec: int,
    inner_cmd: list[str],
) -> tuple[int, str, str]:
    """Возвращает (код выхода процесса timeout, текст лога valgrind, stdout+stderr)."""
    fd, log_path = tempfile.mkstemp(prefix="codesight-vg-", suffix=".log")
    os.close(fd)
    try:
        cmd: list[str] = [
            "timeout",
            str(timeout_sec),
            "valgrind",
            "--tool=memcheck",
            "--leak-check=summary",
            "--errors-for-leak-kinds=all",
            "--error-exitcode=0",
            f"--log-file={log_path}",
            "--quiet",
            *inner_cmd,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out_b, err_b = await proc.communicate()
        combined = (out_b or b"").decode(errors="replace") + (err_b or b"").decode(
            errors="replace"
        )
        with contextlib.suppress(OSError):
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                log_text = fh.read()
        return proc.returncode, _truncate(log_text), _truncate(combined, 8000)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(log_path)


async def run_dynamic_probe(
    project_path: str,
    timeout_sec: int,
) -> tuple[str, str | None]:
    """
    Valgrind + Python в каталоге проекта.

    Сначала пробуем `pytest --collect-only` (без выполнения тестов), при неудаче —
    минимальный интерпретаторный smoke.

    Возвращает (отчёт для БД, сообщение об инфраструктурной ошибке или None).
    """
    if shutil.which("valgrind") is None:
        return "", "valgrind не найден в PATH"

    # 1) pytest только сбор (лёгкая нагрузка на CPython под valgrind)
    code, vg_log, io_tail = await _run_valgrind_subprocess(
        cwd=project_path,
        timeout_sec=timeout_sec,
        inner_cmd=["python3", "-m", "pytest", "--collect-only", "-q", "."],
    )
    if code == 124:
        return (
            vg_log + "\n--- process I/O (tail) ---\n" + io_tail,
            "timeout при pytest --collect-only",
        )

    # коды pytest: 0 ок, 5 нет тестов — для valgrind это нормально
    if code in (0, 5):
        summary = f"pytest --collect-only exit={code}\n"
        return summary + vg_log + "\n--- process I/O (tail) ---\n" + io_tail, None

    # 2) fallback — минимальный запуск интерпретатора
    code2, vg2, io2 = await _run_valgrind_subprocess(
        cwd=project_path,
        timeout_sec=min(timeout_sec, 60),
        inner_cmd=["python3", "-c", "print('codesight-dast-smoke')"],
    )
    if code2 == 124:
        return vg2 + "\n" + io2, "timeout при smoke-команде"

    merged = (
        f"[pytest --collect-only] exit={code}\n{vg_log}\n---\n"
        f"[python smoke] exit={code2}\n{vg2}\n--- I/O ---\n{io_tail}\n{io2}"
    )
    if code2 != 0:
        return merged, f"smoke-команда завершилась с кодом {code2}"
    return merged, None
