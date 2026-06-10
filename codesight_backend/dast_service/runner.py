"""Probe-ориентированный динамический анализ Python-проектов.

Заменяет старый «valgrind + pytest --collect-only» монолит набором независимых
проб, каждая из которых выдаёт структурированный ``ProbeResult``. Падение
одной пробы не валит другие — мы собираем максимум сигнала, который можно
получить из «чёрного ящика» проекта в коротком окне времени.

Состав:

A. ``bytecode_compile`` — ``python -m compileall`` (синтаксис, SyntaxWarning).
B. ``smoke_imports`` — импорт каждого верхнеуровневого пакета/модуля в
   отдельном подпроцессе (ловит ``ImportError`` и побочные эффекты).
C. ``pytest_collect`` — ``python -X dev -W error::ResourceWarning -m pytest
   --collect-only``: количество собранных тестов, ошибки коллекции,
   неосвобождённые ресурсы.
D. ``resource_profile`` — peak RSS / wall time подпроцесса ``pytest
   --collect-only`` через ``resource.getrusage(RUSAGE_CHILDREN)``.
E. ``pip_check`` — статический разбор ``requirements*.txt`` / ``pyproject.toml``:
   количество требований, дубликаты, малосодержательные строки.
F. ``valgrind_memcheck`` — старый valgrind, но запускается ТОЛЬКО при
   обнаружении C-расширений (``*.so``/``*.pyd``/``Extension(``/``*.pyx``).
   На чистом Python пропускается с пояснением.

Точка входа: ``run_dynamic_probes(project_path, timeout_sec) -> DastReport``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, field

# Каталоги, которые пропускаем при поиске .py файлов и пакетов
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "__pycache__",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
        "site-packages",
    }
)


# --------------------------------------------------------------------------- #
# Результаты проб
# --------------------------------------------------------------------------- #


@dataclass
class ProbeResult:
    name: str
    status: str  # ok | warning | error | skipped | timeout
    duration_ms: int = 0
    summary: str = ""
    findings: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    raw_tail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DastReport:
    mode: str  # pure-python | native+memcheck | limited
    probes: list[ProbeResult]
    aggregate: dict
    raw_log: str

    def probes_as_dicts(self) -> list[dict]:
        return [p.to_dict() for p in self.probes]


# --------------------------------------------------------------------------- #
# Низкоуровневая обвязка
# --------------------------------------------------------------------------- #


def _truncate(text: str, max_len: int = 8_000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 60] + "\n… [truncated] …\n"


async def _run_proc(
    cmd: list[str],
    *,
    cwd: str,
    timeout_sec: float,
    env: dict | None = None,
) -> tuple[int, str, str]:
    """Запуск процесса с таймаутом. Возвращает (exit_code, stdout, stderr)."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {exc}"
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=max(timeout_sec, 1.0),
        )
    except asyncio.TimeoutError:
        proc.kill()
        with suppress(ProcessLookupError):
            await proc.wait()
        return 124, "", f"timed out after {timeout_sec:.0f}s"
    code = proc.returncode if proc.returncode is not None else -1
    return (
        code,
        out_b.decode(errors="replace") if out_b else "",
        err_b.decode(errors="replace") if err_b else "",
    )


def _looks_like_no_capabilities(text: str) -> bool:
    """Эвристика для valgrind в rootless-контейнере без CAP_SYS_PTRACE."""
    needles = (
        "Permission denied",
        "Operation not permitted",
        "could not open /proc/self",
        "ptrace",
        "FATAL: ",
    )
    return any(n in text for n in needles)


# --------------------------------------------------------------------------- #
# Обнаружение Python-пакетов и C-расширений
# --------------------------------------------------------------------------- #


def _iter_files(root: str):
    """Ходим по проекту, пропуская служебные каталоги."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for f in filenames:
            yield os.path.join(dirpath, f)


def _detect_top_level_imports(root: str) -> list[str]:
    """Имена топ-уровневых пакетов/модулей, которые имеет смысл пробовать импортировать.

    Пакет = подкаталог с ``__init__.py``, прямой ребёнок ``root``.
    Модуль = ``*.py`` файл прямо в ``root`` (например ``main.py``), кроме служебных.
    """
    names: list[str] = []
    # Имена «не модули, а служебные точки входа» — их импортировать
    # как отдельный top-level бессмысленно (они часть пакета, в котором лежат).
    skip_stems = {"__init__", "__main__", "_version", "version"}
    skip_files = {"setup.py", "conftest.py"}
    for entry in os.scandir(root):
        if entry.is_dir():
            if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            if not entry.name.isidentifier():
                continue
            if os.path.isfile(os.path.join(entry.path, "__init__.py")):
                names.append(entry.name)
        elif entry.is_file() and entry.name.endswith(".py"):
            if entry.name in skip_files:
                continue
            stem = entry.name[:-3]
            if stem in skip_stems:
                continue
            if stem.isidentifier():
                names.append(stem)
    return sorted(set(names))


def _detect_c_extensions(root: str) -> tuple[bool, list[str]]:
    """Есть ли в проекте признаки нативного кода / C-расширений.

    Возвращает (флаг, список «улик»). Триггеры:
    - предкомпилированные модули ``*.so`` (Linux/macOS), ``*.pyd`` (Windows);
    - ``*.pyx`` / ``*.pxd`` (Cython);
    - вызовы ``Extension(`` в ``setup.py``;
    - наличие ``setup.cfg`` или ``pyproject.toml`` с упоминанием
      ``[build-system]`` сборки нативного кода — ловим грубо, по подстроке.
    """
    hits: list[str] = []
    for path in _iter_files(root):
        name = os.path.basename(path)
        rel = os.path.relpath(path, root)
        if name.endswith((".so", ".pyd")):
            hits.append(rel)
        elif name.endswith((".pyx", ".pxd")):
            hits.append(rel)
        elif name == "setup.py":
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
                if "Extension(" in txt or "cythonize(" in txt:
                    hits.append(rel)
            except OSError:
                pass
        if len(hits) >= 10:
            break
    return bool(hits), hits


# --------------------------------------------------------------------------- #
# Парсеры вывода (compileall, pytest)
# --------------------------------------------------------------------------- #


_COMPILE_FAIL_RE = re.compile(
    r"\*{3}\s*(?:Error compiling|Failed to compile)\s+'([^']+)'",
    re.IGNORECASE,
)
_SYNTAX_ERR_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+)\s*\n(?:.*\n)?\s*(.+Error:.+)',
)

_PYTEST_COLLECT_RE = re.compile(
    r"(?:collected|collecting)\s+(\d+)\s+items?",
    re.IGNORECASE,
)
_PYTEST_ERR_COUNT_RE = re.compile(
    r"(\d+)\s+errors?\s+in\s+collection",
    re.IGNORECASE,
)
_PYTEST_ERRORS_BLOCK_RE = re.compile(
    r"^E\s+(.+)$",
    re.MULTILINE,
)


def _parse_compile_errors(stdout: str, stderr: str) -> list[dict]:
    """Достаёт из вывода ``compileall`` список файлов с ошибками компиляции."""
    text = stdout + "\n" + stderr
    findings: list[dict] = []
    seen: set[tuple[str, int | None]] = set()

    for m in _SYNTAX_ERR_RE.finditer(text):
        path = m.group(1)
        line_no = int(m.group(2)) if m.group(2).isdigit() else None
        message = m.group(3).strip()
        key = (path, line_no)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "severity": "error",
                "rule": "SYNTAX_ERROR",
                "file": path,
                "line": line_no,
                "message": message[:300],
            }
        )

    for m in _COMPILE_FAIL_RE.finditer(text):
        path = m.group(1)
        key = (path, None)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            {
                "severity": "error",
                "rule": "COMPILE_FAILED",
                "file": path,
                "line": None,
                "message": "Не удалось скомпилировать модуль до байткода.",
            }
        )

    return findings


def _parse_pytest_output(stdout: str, stderr: str) -> tuple[int, int, list[dict]]:
    """Возвращает (collected, collection_errors, findings)."""
    text = stdout + "\n" + stderr
    collected = 0
    for m in _PYTEST_COLLECT_RE.finditer(text):
        # Берём максимум: разные строки могут показывать промежуточные подсчёты.
        collected = max(collected, int(m.group(1)))

    errors_in_collection = 0
    err_match = _PYTEST_ERR_COUNT_RE.search(text)
    if err_match:
        errors_in_collection = int(err_match.group(1))

    findings: list[dict] = []
    # Ошибки коллекции имеют префикс "E " на строке; собираем коротко.
    e_lines = _PYTEST_ERRORS_BLOCK_RE.findall(text)
    for line in e_lines[:30]:
        msg = line.strip()
        if not msg:
            continue
        findings.append(
            {
                "severity": "error",
                "rule": "PYTEST_COLLECTION_ERROR",
                "file": None,
                "line": None,
                "message": msg[:300],
            }
        )

    # ResourceWarning превращены в исключения через -W error::ResourceWarning.
    for m in re.finditer(r"ResourceWarning:\s*(.+)", text):
        findings.append(
            {
                "severity": "warning",
                "rule": "RESOURCE_WARNING",
                "file": None,
                "line": None,
                "message": m.group(1).strip()[:300],
            }
        )

    return collected, errors_in_collection, findings


# --------------------------------------------------------------------------- #
# Probe A: bytecode_compile
# --------------------------------------------------------------------------- #


async def _probe_bytecode_compile(
    project_path: str, *, timeout_sec: float
) -> ProbeResult:
    started = time.monotonic()
    code, stdout, stderr = await _run_proc(
        ["python3", "-m", "compileall", "-q", "-f", "."],
        cwd=project_path,
        timeout_sec=timeout_sec,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    findings = _parse_compile_errors(stdout, stderr)
    files_failed = len({f["file"] for f in findings if f.get("file")})

    if code == 124:
        status = "timeout"
        summary = "compileall не завершился в отведённое время."
    elif code == 127:
        status = "error"
        summary = "Не найден python3 для запуска compileall."
    elif code == 0 and not findings:
        status = "ok"
        summary = "Все Python-файлы успешно компилируются в байткод."
    elif findings:
        status = "error" if files_failed > 0 else "warning"
        summary = (
            f"Найдено {files_failed} файлов с ошибками компиляции."
            if files_failed
            else "compileall завершился с предупреждениями."
        )
    else:
        status = "warning"
        summary = (
            f"compileall вернул код {code}, явных ошибок не распарсили — см. raw log."
        )

    raw = f"[compileall exit={code}]\n{stdout}\n{stderr}\n"
    return ProbeResult(
        name="bytecode_compile",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        findings=findings,
        metrics={"files_failed": files_failed, "exit_code": code},
        raw_tail=_truncate(raw, 4_000),
    )


# --------------------------------------------------------------------------- #
# Probe B: smoke_imports
# --------------------------------------------------------------------------- #


async def _probe_smoke_imports(project_path: str, *, timeout_sec: float) -> ProbeResult:
    started = time.monotonic()
    names = _detect_top_level_imports(project_path)

    if not names:
        return ProbeResult(
            name="smoke_imports",
            status="skipped",
            duration_ms=int((time.monotonic() - started) * 1000),
            summary="В корне проекта не нашлось топ-уровневых пакетов/модулей.",
            metrics={"imports_total": 0, "imports_failed": 0},
        )

    findings: list[dict] = []
    raw_chunks: list[str] = []
    failed = 0

    # Делим бюджет времени поровну с минимумом 5с на каждый импорт.
    per_import_budget = max(5.0, timeout_sec / max(len(names), 1))

    for name in names:
        # Каждый импорт — в свежем интерпретаторе, чтобы side-effects одного
        # не отравляли другие.
        code, stdout, stderr = await _run_proc(
            ["python3", "-c", f"import {name}"],
            cwd=project_path,
            timeout_sec=min(per_import_budget, timeout_sec),
            env={"PYTHONPATH": project_path},
        )
        raw_chunks.append(
            f"--- import {name} (exit={code}) ---\n{stdout}{stderr}".rstrip()
        )
        if code == 0:
            continue
        failed += 1
        # Достаём «хвост» traceback'а — последняя строка вида ``XError: ...``.
        last_err = ""
        for line in reversed((stdout + "\n" + stderr).splitlines()):
            ls = line.strip()
            if ls.endswith("Error") or ": " in ls and "Error" in ls.split(":")[0]:
                last_err = ls
                break
        if not last_err:
            last_err = "Импорт упал, см. raw log."
        findings.append(
            {
                "severity": "error",
                "rule": "IMPORT_FAILED",
                "file": name,
                "line": None,
                "message": last_err[:300],
            }
        )

    total = len(names)
    duration_ms = int((time.monotonic() - started) * 1000)
    if failed == 0:
        status = "ok"
        summary = f"Все {total} топ-модулей импортируются без ошибок."
    elif failed == total:
        status = "error"
        summary = f"Ни один из {total} топ-модулей не импортируется."
    else:
        status = "error" if failed >= max(1, total // 3) else "warning"
        summary = f"{failed} из {total} топ-модулей упали при импорте."

    return ProbeResult(
        name="smoke_imports",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        findings=findings,
        metrics={
            "imports_total": total,
            "imports_failed": failed,
            "modules": names,
        },
        raw_tail=_truncate("\n\n".join(raw_chunks), 6_000),
    )


# --------------------------------------------------------------------------- #
# Probe C: pytest_collect (dev mode + warnings-as-errors)
# --------------------------------------------------------------------------- #


async def _probe_pytest_collect(
    project_path: str, *, timeout_sec: float
) -> ProbeResult:
    started = time.monotonic()
    code, stdout, stderr = await _run_proc(
        [
            "python3",
            "-X",
            "dev",
            "-W",
            "error::ResourceWarning",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            ".",
        ],
        cwd=project_path,
        timeout_sec=timeout_sec,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    collected, errors, findings = _parse_pytest_output(stdout, stderr)

    # pytest exit codes: 0 OK, 5 no tests collected, 1/2 errors, 4 usage error.
    if code == 124:
        status = "timeout"
        summary = "pytest --collect-only не завершился за отведённое время."
    elif code == 127:
        status = "error"
        summary = "python3 / pytest не найдены в окружении."
    elif code == 5:
        status = "warning"
        summary = "pytest не нашёл тестов (exit=5)."
    elif code == 0:
        status = "ok"
        summary = f"Собрано {collected} тестов без ошибок."
    elif errors > 0 or findings:
        status = "error"
        summary = (
            f"pytest нашёл {errors or len(findings)} ошибок коллекции; "
            f"собрано тестов: {collected}."
        )
    else:
        status = "warning"
        summary = f"pytest вернул код {code}; собрано тестов: {collected}."

    raw = f"[pytest --collect-only exit={code}]\n{stdout}\n{stderr}\n"
    return ProbeResult(
        name="pytest_collect",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        findings=findings,
        metrics={
            "tests_collected": collected,
            "collection_errors": errors,
            "exit_code": code,
        },
        raw_tail=_truncate(raw, 6_000),
    )


# --------------------------------------------------------------------------- #
# Probe D: resource_profile
# --------------------------------------------------------------------------- #


# Маркер для парсинга вывода resource_profile: подпроцесс печатает строку
# вида ``__CS_RUSAGE__ {"rss":..., "utime":..., "stime":...}``.
_RUSAGE_MARKER = "__CS_RUSAGE__"

# Скрипт замера: импортирует топ-пакеты, по факту делает то же, что
# smoke_imports, но в одном процессе → честные ru_maxrss/utime/stime
# для всей сборки. Маркер парсится в _probe_resource_profile.
_RESOURCE_PROBE_PY = f"""
import os, sys, time, json, importlib, resource as _r
sys.path.insert(0, os.getcwd())
names = sorted({{
    d for d in os.listdir('.')
    if os.path.isfile(os.path.join(d, '__init__.py'))
    and d.isidentifier()
}})
loaded = 0
errors = 0
t0 = time.monotonic()
for n in names:
    try:
        importlib.import_module(n)
        loaded += 1
    except Exception:
        errors += 1
elapsed_ms = int((time.monotonic() - t0) * 1000)
ru = _r.getrusage(_r.RUSAGE_SELF)
print('{_RUSAGE_MARKER} ' + json.dumps({{
    'rss_kb': ru.ru_maxrss,
    'utime_ms': int(ru.ru_utime * 1000),
    'stime_ms': int(ru.ru_stime * 1000),
    'imported': loaded,
    'failed': errors,
    'modules': names,
    'inner_wall_ms': elapsed_ms,
}}))
"""


def _parse_rusage_marker(text: str) -> dict | None:
    for line in reversed(text.splitlines()):
        if line.startswith(_RUSAGE_MARKER):
            payload = line[len(_RUSAGE_MARKER) :].strip()
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
    return None


async def _probe_resource_profile(
    project_path: str, *, timeout_sec: float
) -> ProbeResult:
    started = time.monotonic()
    code, stdout, stderr = await _run_proc(
        ["python3", "-c", _RESOURCE_PROBE_PY],
        cwd=project_path,
        timeout_sec=timeout_sec,
        env={"PYTHONPATH": project_path},
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    payload = _parse_rusage_marker(stdout) or {}
    rss_kb = int(payload.get("rss_kb", 0))
    utime_ms = int(payload.get("utime_ms", 0))
    stime_ms = int(payload.get("stime_ms", 0))
    loaded = int(payload.get("imported", 0))
    failed = int(payload.get("failed", 0))
    modules = payload.get("modules", [])

    metrics = {
        "peak_rss_kb": rss_kb,
        "wall_time_ms": duration_ms,
        "inner_wall_ms": int(payload.get("inner_wall_ms", 0)),
        "cpu_user_ms": utime_ms,
        "cpu_sys_ms": stime_ms,
        "imported": loaded,
        "failed": failed,
        "modules_count": len(modules),
        "exit_code": code,
    }

    if code == 124:
        status = "timeout"
        summary = (
            "Импорт-проба не уложилась в таймаут — кодовая база тяжёлая или зависла."
        )
    elif code == 127:
        status = "error"
        summary = "python3 не найден в окружении."
    elif not payload:
        status = "warning"
        summary = (
            f"Подпроцесс вернул код {code}, но маркер rusage в выводе не найден; "
            "см. raw log."
        )
    elif code != 0:
        status = "warning"
        summary = (
            f"Импорт-проба упала (exit={code}); базовые ресурсы интерпретатора "
            f"всё же померяны (RSS ≈ {rss_kb / 1024:.1f} MiB)."
        )
    else:
        summary = (
            f"Peak RSS ≈ {rss_kb / 1024:.1f} MiB, "
            f"wall {duration_ms} ms (user {utime_ms} ms / sys {stime_ms} ms); "
            f"импортировано {loaded}/{loaded + failed} топ-пакетов."
        )
        status = "warning" if failed > 0 else "ok"

    return ProbeResult(
        name="resource_profile",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        metrics=metrics,
        raw_tail=_truncate(stdout + "\n" + stderr, 2_000),
    )


# --------------------------------------------------------------------------- #
# Probe E: pip_check (static)
# --------------------------------------------------------------------------- #


# Имя пакета по PEP 508: буквы/цифры/_-., опциональные ``[extras]``,
# затем спецификатор версии (``==``, ``>=``, ``~=``, ``@`` и т.д.) или просто
# конец строки (для непривязанных требований вида ``requests``).
_REQ_LINE_RE = re.compile(
    r"^\s*"
    r"(?P<name>[A-Za-z0-9_.\-]+)"
    r"(?:\[[A-Za-z0-9_.,\- ]+\])?"  # extras: foo[a,b]
    r"\s*"
    r"(?:(?P<op>===|==|<=|>=|!=|~=|<|>|@)\s*\S+.*)?"
    r"\s*$",
)


def _parse_requirements_file(path: str) -> tuple[list[str], list[str]]:
    """Возвращает (packages, malformed_lines)."""
    packages: list[str] = []
    malformed: list[str] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                # Срезаем хвост-комментарий вида `pkg==1.0  # comment`.
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                if line.startswith("-"):  # -e, -r, --hash и т.д.
                    continue
                m = _REQ_LINE_RE.match(line)
                if m:
                    packages.append(m.group("name").lower())
                else:
                    malformed.append(raw.rstrip())
    except OSError:
        pass
    return packages, malformed


async def _probe_pip_check(project_path: str, *, timeout_sec: float) -> ProbeResult:
    started = time.monotonic()

    req_files: list[str] = []
    for name in ("requirements.txt", "requirements-dev.txt", "dev-requirements.txt"):
        path = os.path.join(project_path, name)
        if os.path.isfile(path):
            req_files.append(path)
    # Дополнительно — стандартный requirements/ каталог
    req_dir = os.path.join(project_path, "requirements")
    if os.path.isdir(req_dir):
        for entry in os.scandir(req_dir):
            if entry.is_file() and entry.name.endswith(".txt"):
                req_files.append(entry.path)

    pyproject = os.path.join(project_path, "pyproject.toml")
    has_pyproject = os.path.isfile(pyproject)

    if not req_files and not has_pyproject:
        return ProbeResult(
            name="pip_check",
            status="skipped",
            duration_ms=int((time.monotonic() - started) * 1000),
            summary="Не найдено requirements*.txt / pyproject.toml.",
            metrics={"total_requirements": 0},
        )

    all_packages: list[str] = []
    malformed: list[str] = []
    for rf in req_files:
        pkgs, mal = _parse_requirements_file(rf)
        all_packages.extend(pkgs)
        malformed.extend(mal)

    # Дубликаты (одна и та же библиотека может появиться с разными версиями
    # в нескольких файлах — это часто источник конфликтов).
    seen: dict[str, int] = {}
    for p in all_packages:
        seen[p] = seen.get(p, 0) + 1
    duplicates = [name for name, count in seen.items() if count > 1]

    findings: list[dict] = []
    for line in malformed[:20]:
        findings.append(
            {
                "severity": "warning",
                "rule": "MALFORMED_REQUIREMENT",
                "file": "requirements",
                "line": None,
                "message": f"Не удалось распарсить строку: {line[:120]}",
            }
        )
    for dup in duplicates[:20]:
        findings.append(
            {
                "severity": "warning",
                "rule": "DUPLICATE_REQUIREMENT",
                "file": "requirements",
                "line": None,
                "message": f"Пакет '{dup}' указан более одного раза.",
            }
        )

    # Дополнительно прогоняем `pip check` в текущем окружении контейнера.
    # Это НЕ проверяет deps пользователя (мы их не устанавливаем без сети),
    # но ловит ситуацию, когда наш собственный env сломан → значит и наши
    # измерения в C/D могли быть невалидны.
    pip_code, pip_out, pip_err = await _run_proc(
        ["python3", "-m", "pip", "check"],
        cwd=project_path,
        timeout_sec=min(timeout_sec, 30.0),
    )
    if pip_code not in (0, 127) and (pip_out.strip() or pip_err.strip()):
        findings.append(
            {
                "severity": "warning",
                "rule": "ENV_PIP_CHECK_DIRTY",
                "file": "<runtime>",
                "line": None,
                "message": (
                    "В контейнере dast_service pip check вернул сообщения — "
                    "это может влиять на точность probes C/D."
                ),
            }
        )

    total_requirements = len(all_packages)
    unique_requirements = len(seen)
    # «Pinned» — строка вида ``foo==1.2.3``. Считаем по сырому тексту, чтобы
    # не зависеть от того, как _REQ_LINE_RE расклассифицировал строку.
    pinned = 0
    for rf in req_files:
        with suppress(OSError):
            with open(rf, encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    if "==" in raw and not raw.lstrip().startswith("#"):
                        pinned += 1

    duration_ms = int((time.monotonic() - started) * 1000)
    summary = (
        f"Файлов: {len(req_files)}{' + pyproject.toml' if has_pyproject else ''}; "
        f"требований: {total_requirements} (уникальных {unique_requirements}, "
        f"закреплённых {pinned}); дубликатов: {len(duplicates)}; "
        f"malformed: {len(malformed)}."
    )
    if findings:
        status = "warning"
    else:
        status = "ok"

    raw = (
        f"[requirements files: {req_files}]\n"
        f"duplicates: {duplicates}\n"
        f"malformed: {malformed[:5]}\n"
        f"[pip check exit={pip_code}]\n{pip_out}\n{pip_err}\n"
    )
    return ProbeResult(
        name="pip_check",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        findings=findings,
        metrics={
            "total_requirements": total_requirements,
            "unique_requirements": unique_requirements,
            "pinned_requirements": pinned,
            "duplicates_count": len(duplicates),
            "malformed_count": len(malformed),
            "has_pyproject_toml": has_pyproject,
        },
        raw_tail=_truncate(raw, 3_000),
    )


# --------------------------------------------------------------------------- #
# Probe F: valgrind_memcheck (только при наличии C-расширений)
# --------------------------------------------------------------------------- #


async def _probe_valgrind_memcheck(
    project_path: str,
    *,
    timeout_sec: float,
    c_ext_hits: list[str],
) -> ProbeResult:
    started = time.monotonic()

    if not c_ext_hits:
        return ProbeResult(
            name="valgrind_memcheck",
            status="skipped",
            duration_ms=int((time.monotonic() - started) * 1000),
            summary=(
                "В проекте не найдено C-расширений (*.so / *.pyd / *.pyx / "
                "Extension(...)) — memcheck бесполезен для чистого Python."
            ),
            metrics={"c_extension_hits": []},
        )

    if shutil.which("valgrind") is None:
        return ProbeResult(
            name="valgrind_memcheck",
            status="skipped",
            duration_ms=int((time.monotonic() - started) * 1000),
            summary="valgrind отсутствует в PATH контейнера.",
            metrics={"c_extension_hits": c_ext_hits},
        )

    log_path = os.path.join("/tmp", f"codesight-vg-{os.getpid()}.log")
    cmd = [
        "valgrind",
        "--tool=memcheck",
        "--leak-check=summary",
        "--errors-for-leak-kinds=all",
        "--error-exitcode=0",
        f"--log-file={log_path}",
        "--quiet",
        "python3",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        ".",
    ]
    try:
        code, stdout, stderr = await _run_proc(
            cmd, cwd=project_path, timeout_sec=timeout_sec
        )
    finally:
        pass
    duration_ms = int((time.monotonic() - started) * 1000)

    log_text = ""
    with suppress(OSError):
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            log_text = fh.read()
    with suppress(OSError):
        os.unlink(log_path)

    combined = stdout + "\n" + stderr + "\n" + log_text

    if code == 124:
        status = "timeout"
        summary = "valgrind+pytest не завершился за отведённое время."
    elif _looks_like_no_capabilities(combined):
        status = "skipped"
        summary = (
            "valgrind недоступен в rootless-контейнере без CAP_SYS_PTRACE. "
            "Запустите orchestrator с расширенными capabilities, чтобы получить memcheck."
        )
    elif code in (0, 5):
        # Парсим ERROR SUMMARY / definitely lost из лога.
        m_err = re.search(r"ERROR SUMMARY:\s*(\d+)\s+errors", log_text)
        m_leak = re.search(r"definitely lost:\s*([\d,]+)\s+bytes", log_text)
        errors_n = int(m_err.group(1)) if m_err else 0
        leak_b = int(m_leak.group(1).replace(",", "")) if m_leak else 0
        if errors_n == 0 and leak_b == 0:
            status = "ok"
            summary = "memcheck: ошибок не найдено."
        else:
            status = "warning"
            summary = f"memcheck: {errors_n} ошибок, definitely lost: {leak_b} байт."
    else:
        status = "warning"
        summary = f"valgrind вернул код {code}; см. raw log."

    findings: list[dict] = []
    # Грубо вытащим первые 5 «возможных утечек» / ошибок из лога.
    for m in re.finditer(
        r"==\d+==\s+(Invalid (?:read|write).+?|Conditional jump.+?|definitely lost.+?|Mismatched.+?)$",
        log_text,
        re.MULTILINE,
    ):
        findings.append(
            {
                "severity": "warning",
                "rule": "VALGRIND_MEMCHECK",
                "file": None,
                "line": None,
                "message": m.group(1).strip()[:300],
            }
        )
        if len(findings) >= 5:
            break

    raw = (
        f"[valgrind exit={code}]\n--- log ---\n{log_text}\n"
        f"--- io ---\n{stdout}\n{stderr}\n"
    )
    return ProbeResult(
        name="valgrind_memcheck",
        status=status,
        duration_ms=duration_ms,
        summary=summary,
        findings=findings,
        metrics={
            "c_extension_hits": c_ext_hits[:20],
            "exit_code": code,
        },
        raw_tail=_truncate(raw, 8_000),
    )


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #


def _allocate_budget(total: int) -> dict[str, float]:
    """Грубо делит общий бюджет (сек) между probes по их типичному «весу»."""
    # Веса подобраны эмпирически: pytest collect и valgrind — самые тяжёлые.
    weights = {
        "bytecode_compile": 1.0,
        "smoke_imports": 2.0,
        "pytest_collect": 3.5,
        "resource_profile": 2.0,
        "pip_check": 0.5,
        "valgrind_memcheck": 4.0,
    }
    s = sum(weights.values())
    return {k: max(5.0, total * w / s) for k, w in weights.items()}


def _aggregate(probes: list[ProbeResult]) -> dict:
    """Сводные счётчики и метрики по всем probes."""
    findings = [f for p in probes for f in p.findings]
    by_sev: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "info")
        by_sev[sev] = by_sev.get(sev, 0) + 1
    by_status: dict[str, int] = {}
    for p in probes:
        by_status[p.status] = by_status.get(p.status, 0) + 1

    # Извлекаем «киллер-метрики», на которые имеет смысл смотреть в UI.
    metrics_flat: dict = {}
    for p in probes:
        for k, v in p.metrics.items():
            metrics_flat[f"{p.name}.{k}"] = v

    return {
        "total_probes": len(probes),
        "findings_total": len(findings),
        "findings_by_severity": by_sev,
        "probes_by_status": by_status,
        "metrics": metrics_flat,
    }


async def run_dynamic_probes(
    project_path: str,
    timeout_sec: int,
) -> DastReport:
    """Главная точка входа: запускает все probes и собирает ``DastReport``."""
    if not os.path.isdir(project_path):
        return DastReport(
            mode="limited",
            probes=[
                ProbeResult(
                    name="bootstrap",
                    status="error",
                    summary=f"Каталог проекта не найден: {project_path}",
                )
            ],
            aggregate={"total_probes": 0, "findings_total": 0},
            raw_log=f"project_path not found: {project_path}",
        )

    has_c_ext, c_ext_hits = _detect_c_extensions(project_path)
    mode = "native+memcheck" if has_c_ext else "pure-python"

    budget = _allocate_budget(timeout_sec)
    probes: list[ProbeResult] = []

    # Probes идут последовательно, чтобы не конкурировать за CPU/RAM в slim-контейнере.
    probes.append(
        await _probe_bytecode_compile(
            project_path, timeout_sec=budget["bytecode_compile"]
        )
    )
    probes.append(
        await _probe_smoke_imports(project_path, timeout_sec=budget["smoke_imports"])
    )
    probes.append(
        await _probe_pytest_collect(project_path, timeout_sec=budget["pytest_collect"])
    )
    probes.append(
        await _probe_resource_profile(
            project_path, timeout_sec=budget["resource_profile"]
        )
    )
    probes.append(await _probe_pip_check(project_path, timeout_sec=budget["pip_check"]))
    probes.append(
        await _probe_valgrind_memcheck(
            project_path,
            timeout_sec=budget["valgrind_memcheck"],
            c_ext_hits=c_ext_hits,
        )
    )

    aggregate = _aggregate(probes)
    raw_log = (
        f"[dast mode = {mode}]\n"
        f"detected C-extension hits: {c_ext_hits[:10]}\n\n"
        + "\n\n".join(
            f"=== {p.name} ({p.status}, {p.duration_ms} ms) ===\n{p.summary}\n{p.raw_tail}"
            for p in probes
        )
    )

    return DastReport(
        mode=mode,
        probes=probes,
        aggregate=aggregate,
        raw_log=raw_log,
    )


# --------------------------------------------------------------------------- #
# Совместимость: старая точка входа run_dynamic_probe
# --------------------------------------------------------------------------- #


async def run_dynamic_probe(
    project_path: str,
    timeout_sec: int,
) -> tuple[str, str | None]:
    """Адаптер для старого call-site'а: возвращает (raw_log, infra_warning).

    Сохраняем интерфейс на случай, если кто-то импортирует напрямую.
    Внутри теперь работает probe-based анализ.
    """
    report = await run_dynamic_probes(project_path, timeout_sec)
    has_error = any(p.status == "error" for p in report.probes)
    infra: str | None
    if has_error:
        infra = "Некоторые probes завершились с ошибкой — см. структурированный отчёт."
    else:
        infra = None
    return report.raw_log, infra


def serialize_report(report: DastReport) -> str:
    """JSON-сериализация полного отчёта (для тестов и raw debug)."""
    return json.dumps(
        {
            "mode": report.mode,
            "probes": report.probes_as_dicts(),
            "aggregate": report.aggregate,
        },
        ensure_ascii=False,
        indent=2,
    )


__all__ = [
    "DastReport",
    "ProbeResult",
    "run_dynamic_probe",
    "run_dynamic_probes",
    "serialize_report",
]
