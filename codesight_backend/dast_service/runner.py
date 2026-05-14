"""Запуск Valgrind вокруг лёгкой динамической проверки Python в каталоге проекта."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from contextlib import suppress


def _truncate(text: str, max_len: int = 120_000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 80] + "\n\n… [truncated] …\n"


async def _run_process(
    cmd: list[str],
    *,
    cwd: str,
    timeout_sec: int,
) -> tuple[int, bytes, bytes]:
    """Запуск процесса с таймаутом (без внешней команды GNU `timeout` — совместимость с slim-образами)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=float(timeout_sec),
        )
    except asyncio.TimeoutError:
        proc.kill()
        with suppress(ProcessLookupError):
            await proc.wait()
        return 124, b"", b"asyncio.TimeoutError: process killed after timeout\n"
    code = proc.returncode if proc.returncode is not None else -1
    return code, out_b or b"", err_b or b""


async def _run_valgrind_subprocess(
    *,
    cwd: str,
    timeout_sec: int,
    inner_cmd: list[str],
) -> tuple[int, str, str]:
    """Возвращает (код выхода, текст лога valgrind, stdout+stderr)."""
    fd, log_path = tempfile.mkstemp(prefix="codesight-vg-", suffix=".log")
    os.close(fd)
    try:
        cmd: list[str] = [
            "valgrind",
            "--tool=memcheck",
            "--leak-check=summary",
            "--errors-for-leak-kinds=all",
            "--error-exitcode=0",
            f"--log-file={log_path}",
            "--quiet",
            *inner_cmd,
        ]
        code, out_b, err_b = await _run_process(cmd, cwd=cwd, timeout_sec=timeout_sec)
        combined = out_b.decode(errors="replace") + err_b.decode(errors="replace")
        with suppress(OSError):
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                log_text = fh.read()
        return code, _truncate(log_text), _truncate(combined, 8000)
    finally:
        with suppress(OSError):
            os.unlink(log_path)


def _looks_like_no_capabilities(text: str) -> bool:
    """Heuristics: valgrind не смог получить нужные права в rootless-контейнере."""
    needles = (
        "Permission denied",
        "Operation not permitted",
        "could not open /proc/self",
        "EPERM",
        "ptrace",
        "FATAL: ",
    )
    return any(n in text for n in needles)


async def _run_python_subprocess(
    *,
    cwd: str,
    timeout_sec: int,
    inner_cmd: list[str],
) -> tuple[int, str]:
    """Запустить Python-команду. Возвращает (code, stdout+stderr)."""
    code, out_b, err_b = await _run_process(inner_cmd, cwd=cwd, timeout_sec=timeout_sec)
    combined = out_b.decode(errors="replace") + err_b.decode(errors="replace")
    return code, _truncate(combined, 16_000)


async def run_dynamic_probe(
    project_path: str,
    timeout_sec: int,
) -> tuple[str, str | None]:
    """
    Динамический анализ Python-проекта.

    Алгоритм:
        1. Если есть valgrind — пробуем `pytest --collect-only` под valgrind.
        2. Если valgrind отсутствует или не может работать (rootless без
           CAP_SYS_PTRACE, например), переходим на чистый Python-смок.
    """
    have_valgrind = shutil.which("valgrind") is not None

    if have_valgrind:
        code, vg_log, io_tail = await _run_valgrind_subprocess(
            cwd=project_path,
            timeout_sec=timeout_sec,
            inner_cmd=["python3", "-m", "pytest", "--collect-only", "-q", "."],
        )
        merged = (
            f"[valgrind + pytest --collect-only] exit={code}\n"
            f"--- valgrind log ---\n{vg_log}\n"
            f"--- process I/O (tail) ---\n{io_tail}\n"
        )
        if code == 124:
            return merged, "timeout при pytest --collect-only"
        if code in (0, 5):
            return merged, None

        if _looks_like_no_capabilities(vg_log + "\n" + io_tail):
            note = (
                "valgrind недоступен в текущем окружении "
                "(rootless контейнер без CAP_SYS_PTRACE). "
                "Запускаем чистый Python-смок.\n\n"
            )
        else:
            note = "valgrind вернул ненулевой код, пробуем чистый Python-смок.\n\n"

        code2, py_out = await _run_python_subprocess(
            cwd=project_path,
            timeout_sec=min(timeout_sec, 60),
            inner_cmd=["python3", "-m", "pytest", "--collect-only", "-q", "."],
        )
        code3, smoke_out = await _run_python_subprocess(
            cwd=project_path,
            timeout_sec=min(timeout_sec, 30),
            inner_cmd=["python3", "-c", "print('codesight-dast-smoke')"],
        )
        merged2 = (
            note
            + merged
            + f"\n[pytest --collect-only без valgrind] exit={code2}\n{py_out}\n"
            + f"\n[python smoke без valgrind] exit={code3}\n{smoke_out}\n"
        )
        if code3 == 0 and code2 not in (0, 5):
            return (
                merged2,
                f"pytest --collect-only завершился с кодом {code2} (сохранён частичный отчёт; smoke OK)",
            )
        ok = code2 in (0, 5) and code3 == 0
        return (
            merged2,
            None
            if ok
            else (
                "valgrind/python smoke завершились с ошибками "
                f"(pytest={code2}, smoke={code3})"
            ),
        )

    note = "valgrind не найден в PATH — выполняется чистый Python-смок.\n\n"
    code2, py_out = await _run_python_subprocess(
        cwd=project_path,
        timeout_sec=timeout_sec,
        inner_cmd=["python3", "-m", "pytest", "--collect-only", "-q", "."],
    )
    code3, smoke_out = await _run_python_subprocess(
        cwd=project_path,
        timeout_sec=min(timeout_sec, 30),
        inner_cmd=["python3", "-c", "print('codesight-dast-smoke')"],
    )
    merged = (
        note
        + f"[pytest --collect-only] exit={code2}\n{py_out}\n"
        + f"\n[python smoke] exit={code3}\n{smoke_out}\n"
    )
    if code3 == 0 and code2 not in (0, 5):
        return (
            merged,
            f"pytest --collect-only завершился с кодом {code2} (частичный отчёт; smoke OK)",
        )
    ok = code2 in (0, 5) and code3 == 0
    return (
        merged,
        None if ok else f"smoke завершился с ошибками (pytest={code2}, smoke={code3})",
    )
