"""Проверки безопасности по модели OWASP Top 10.

Каждый checker возвращает список RawFinding.
Все чекеры запускаются параллельно через run_all().

OWASP Top 10 (2021):
  A01 - Broken Access Control
  A02 - Cryptographic Failures
  A03 - Injection
  A04 - Insecure Design
  A05 - Security Misconfiguration
  A06 - Vulnerable and Outdated Components
  A07 - Identification and Authentication Failures
  A08 - Software and Data Integrity Failures
  A09 - Security Logging and Monitoring Failures
  A10 - Server-Side Request Forgery (SSRF)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawFinding:
    owasp_category: str  # A01..A10
    owasp_title: str
    checker: str
    severity: str  # critical | high | medium | low | info
    file_path: str
    line: int | None
    column: int | None
    code: str | None
    message: str
    cwe: str | None = None


async def _run(cmd: list[str], cwd: str) -> tuple[str, str, int]:
    """Запустить subprocess асинхронно."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return (
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
        proc.returncode,
    )


# ---------------------------------------------------------------------------
# OWASP маппинг для bandit test_id -> (category, title, cwe, severity)
# ---------------------------------------------------------------------------

BANDIT_OWASP_MAP: dict[str, tuple[str, str, str | None, str]] = {
    # A01 - Broken Access Control
    "B105": ("A01", "Broken Access Control", "CWE-732", "medium"),
    "B106": ("A01", "Broken Access Control", "CWE-732", "medium"),
    "B107": ("A01", "Broken Access Control", "CWE-732", "low"),
    "B108": ("A01", "Broken Access Control", "CWE-732", "medium"),
    # A02 - Cryptographic Failures
    "B303": ("A02", "Cryptographic Failures", "CWE-327", "high"),
    "B304": ("A02", "Cryptographic Failures", "CWE-327", "high"),
    "B305": ("A02", "Cryptographic Failures", "CWE-327", "medium"),
    "B306": ("A02", "Cryptographic Failures", "CWE-327", "medium"),
    "B323": ("A02", "Cryptographic Failures", "CWE-327", "medium"),
    "B324": ("A02", "Cryptographic Failures", "CWE-916", "high"),
    "B501": ("A02", "Cryptographic Failures", "CWE-295", "high"),
    "B502": ("A02", "Cryptographic Failures", "CWE-295", "high"),
    "B503": ("A02", "Cryptographic Failures", "CWE-295", "medium"),
    "B504": ("A02", "Cryptographic Failures", "CWE-295", "low"),
    "B505": ("A02", "Cryptographic Failures", "CWE-326", "critical"),
    "B506": ("A02", "Cryptographic Failures", "CWE-327", "medium"),
    # A03 - Injection
    "B101": ("A03", "Injection", "CWE-703", "low"),
    "B102": ("A03", "Injection", "CWE-78", "high"),
    "B103": ("A03", "Injection", "CWE-78", "high"),
    "B104": ("A03", "Injection", "CWE-605", "medium"),
    "B201": ("A03", "Injection", "CWE-78", "high"),
    "B202": ("A03", "Injection", "CWE-78", "high"),
    "B301": ("A03", "Injection", "CWE-502", "medium"),
    "B302": ("A03", "Injection", "CWE-502", "medium"),
    "B307": ("A03", "Injection", "CWE-78", "medium"),
    "B308": ("A03", "Injection", "CWE-79", "medium"),
    "B310": ("A03", "Injection", "CWE-601", "medium"),
    "B311": ("A03", "Injection", "CWE-338", "low"),
    "B312": ("A03", "Injection", "CWE-605", "low"),
    "B313": ("A03", "Injection", "CWE-611", "medium"),
    "B314": ("A03", "Injection", "CWE-611", "medium"),
    "B315": ("A03", "Injection", "CWE-611", "low"),
    "B316": ("A03", "Injection", "CWE-611", "low"),
    "B317": ("A03", "Injection", "CWE-611", "medium"),
    "B318": ("A03", "Injection", "CWE-611", "medium"),
    "B319": ("A03", "Injection", "CWE-611", "medium"),
    "B320": ("A03", "Injection", "CWE-611", "medium"),
    "B325": ("A03", "Injection", "CWE-362", "medium"),
    "B601": ("A03", "Injection", "CWE-78", "high"),
    "B602": ("A03", "Injection", "CWE-78", "critical"),
    "B603": ("A03", "Injection", "CWE-78", "low"),
    "B604": ("A03", "Injection", "CWE-78", "high"),
    "B605": ("A03", "Injection", "CWE-78", "high"),
    "B606": ("A03", "Injection", "CWE-78", "medium"),
    "B607": ("A03", "Injection", "CWE-78", "low"),
    "B608": ("A03", "Injection", "CWE-89", "high"),
    "B609": ("A03", "Injection", "CWE-78", "high"),
    "B610": ("A03", "Injection", "CWE-89", "medium"),
    "B611": ("A03", "Injection", "CWE-89", "high"),
    # A05 - Security Misconfiguration
    "B401": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B402": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B403": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B404": ("A05", "Security Misconfiguration", "CWE-78", "low"),
    "B405": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B406": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B407": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B408": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B409": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B410": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B411": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B412": ("A05", "Security Misconfiguration", "CWE-676", "low"),
    "B413": ("A05", "Security Misconfiguration", "CWE-327", "high"),
    # A07 - Identification and Authentication Failures
    "B703": ("A07", "Identification and Authentication Failures", "CWE-78", "high"),
    "B704": ("A07", "Identification and Authentication Failures", "CWE-78", "high"),
}

# Дефолтный маппинг для неизвестных bandit ID
BANDIT_SEVERITY_MAP: dict[str, str] = {
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNDEFINED": "info",
}


# ---------------------------------------------------------------------------
# A03 / A10 / A05 — regex-чекер по исходникам
# ---------------------------------------------------------------------------


@dataclass
class RegexRule:
    pattern: re.Pattern[str]
    owasp_category: str
    owasp_title: str
    severity: str
    code: str
    message: str
    cwe: str | None = None


REGEX_RULES: list[RegexRule] = [
    # A03 — SQL Injection (raw string в запросе)
    RegexRule(
        pattern=re.compile(
            r'(execute|cursor\.execute|raw|RawSQL)\s*\(\s*[f"].*%(s|d)|\+.*WHERE|format\s*\(.*WHERE',
            re.IGNORECASE,
        ),
        owasp_category="A03",
        owasp_title="Injection",
        severity="high",
        code="SEC-SQL-001",
        message="Possible SQL injection: string formatting inside query",
        cwe="CWE-89",
    ),
    # A03 — Command Injection
    RegexRule(
        pattern=re.compile(
            r"os\.system\s*\(|subprocess\.call\s*\(.*shell\s*=\s*True|subprocess\.Popen\s*\(.*shell\s*=\s*True",
            re.IGNORECASE,
        ),
        owasp_category="A03",
        owasp_title="Injection",
        severity="high",
        code="SEC-CMD-001",
        message="Command injection risk: shell=True or os.system() with user-controlled input",
        cwe="CWE-78",
    ),
    # A03 — Path Traversal
    RegexRule(
        pattern=re.compile(
            r'open\s*\(.*\+|open\s*\(.*format\s*\(|open\s*\(.*f["\']',
            re.IGNORECASE,
        ),
        owasp_category="A03",
        owasp_title="Injection",
        severity="medium",
        code="SEC-PATH-001",
        message="Possible path traversal: file path constructed from user input",
        cwe="CWE-22",
    ),
    # A02 — Hardcoded secret / password
    RegexRule(
        pattern=re.compile(
            r'(password|passwd|secret|api_key|apikey|token|private_key)\s*=\s*["\'][^"\']{4,}["\']',
            re.IGNORECASE,
        ),
        owasp_category="A02",
        owasp_title="Cryptographic Failures",
        severity="high",
        code="SEC-CRED-001",
        message="Hardcoded credential detected in source code",
        cwe="CWE-798",
    ),
    # A02 — MD5/SHA1 weak hash
    RegexRule(
        pattern=re.compile(
            r"hashlib\.(md5|sha1)\s*\(",
            re.IGNORECASE,
        ),
        owasp_category="A02",
        owasp_title="Cryptographic Failures",
        severity="medium",
        code="SEC-HASH-001",
        message="Weak hashing algorithm (MD5/SHA1) used — prefer SHA-256 or stronger",
        cwe="CWE-327",
    ),
    # A02 — HTTP (not HTTPS)
    RegexRule(
        pattern=re.compile(
            r'["\']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)',
            re.IGNORECASE,
        ),
        owasp_category="A02",
        owasp_title="Cryptographic Failures",
        severity="low",
        code="SEC-TLS-001",
        message="Unencrypted HTTP URL found — prefer HTTPS",
        cwe="CWE-319",
    ),
    # A05 — Debug mode enabled
    RegexRule(
        pattern=re.compile(
            r"DEBUG\s*=\s*True|app\.run\s*\(.*debug\s*=\s*True",
            re.IGNORECASE,
        ),
        owasp_category="A05",
        owasp_title="Security Misconfiguration",
        severity="medium",
        code="SEC-CFG-001",
        message="Debug mode is enabled — must be disabled in production",
        cwe="CWE-94",
    ),
    # A05 — eval / exec
    RegexRule(
        pattern=re.compile(
            r"\beval\s*\(|\bexec\s*\(",
            re.IGNORECASE,
        ),
        owasp_category="A05",
        owasp_title="Security Misconfiguration",
        severity="high",
        code="SEC-EVAL-001",
        message="Use of eval()/exec() is dangerous and may allow arbitrary code execution",
        cwe="CWE-95",
    ),
    # A07 — JWT none algorithm
    RegexRule(
        pattern=re.compile(
            r'algorithm\s*=\s*["\']none["\']|algorithms\s*=\s*\[["\']none["\']',
            re.IGNORECASE,
        ),
        owasp_category="A07",
        owasp_title="Identification and Authentication Failures",
        severity="critical",
        code="SEC-JWT-001",
        message="JWT 'none' algorithm is insecure — always validate signature",
        cwe="CWE-347",
    ),
    # A07 — Insecure cookie (no httponly/secure)
    RegexRule(
        pattern=re.compile(
            r"set_cookie\s*\((?![^)]*httponly\s*=\s*True)",
            re.IGNORECASE,
        ),
        owasp_category="A07",
        owasp_title="Identification and Authentication Failures",
        severity="medium",
        code="SEC-COOK-001",
        message="Cookie set without httponly=True — vulnerable to XSS session hijacking",
        cwe="CWE-614",
    ),
    # A10 — SSRF via requests with user input
    RegexRule(
        pattern=re.compile(
            r"requests\.(get|post|put|delete|patch)\s*\(\s*(url|request\.)",
            re.IGNORECASE,
        ),
        owasp_category="A10",
        owasp_title="Server-Side Request Forgery (SSRF)",
        severity="medium",
        code="SEC-SSRF-001",
        message="Possible SSRF: HTTP request with potentially user-controlled URL",
        cwe="CWE-918",
    ),
    # A09 — No logging for exceptions
    RegexRule(
        pattern=re.compile(
            r"except\s+[\w,\s]*:\s*\n\s*pass",
            re.IGNORECASE,
        ),
        owasp_category="A09",
        owasp_title="Security Logging and Monitoring Failures",
        severity="low",
        code="SEC-LOG-001",
        message="Silent exception handler (bare pass) — security events may go unlogged",
        cwe="CWE-390",
    ),
]

PYTHON_EXTENSIONS = {".py"}


def _collect_python_files(project_path: str) -> list[Path]:
    root = Path(project_path)
    return [
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix in PYTHON_EXTENSIONS
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
    ]


# ---------------------------------------------------------------------------
# Bandit-based checker (A01..A07)
# ---------------------------------------------------------------------------


async def run_bandit_security(project_path: str) -> list[RawFinding]:
    """Запустить bandit и сопоставить результаты с OWASP категориями."""
    stdout, _, _ = await _run(
        ["bandit", "-r", ".", "-f", "json", "-q"],
        cwd=project_path,
    )
    findings: list[RawFinding] = []
    if not stdout.strip():
        return findings
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return findings

    for item in data.get("results", []):
        test_id: str = item.get("test_id", "").upper()
        raw_sev: str = item.get("issue_severity", "UNDEFINED").upper()

        if test_id in BANDIT_OWASP_MAP:
            category, title, cwe, severity = BANDIT_OWASP_MAP[test_id]
        else:
            # Неизвестный тест — относим к A05 Security Misconfiguration
            category = "A05"
            title = "Security Misconfiguration"
            cwe = None
            severity = BANDIT_SEVERITY_MAP.get(raw_sev, "medium")

        findings.append(
            RawFinding(
                owasp_category=category,
                owasp_title=title,
                checker="bandit",
                severity=severity,
                file_path=os.path.relpath(item.get("filename", ""), project_path),
                line=item.get("line_number"),
                column=None,
                code=test_id or None,
                message=item.get("issue_text", ""),
                cwe=cwe,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Regex-based checker (дополнительные паттерны по всем OWASP категориям)
# ---------------------------------------------------------------------------


async def run_regex_security(project_path: str) -> list[RawFinding]:
    """Сканировать исходники регулярными выражениями."""
    findings: list[RawFinding] = []
    py_files = _collect_python_files(project_path)

    for file_path in py_files:
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel_path = os.path.relpath(str(file_path), project_path)
        lines = source.splitlines()

        for rule in REGEX_RULES:
            for line_no, line_content in enumerate(lines, start=1):
                if rule.pattern.search(line_content):
                    findings.append(
                        RawFinding(
                            owasp_category=rule.owasp_category,
                            owasp_title=rule.owasp_title,
                            checker="regex",
                            severity=rule.severity,
                            file_path=rel_path,
                            line=line_no,
                            column=None,
                            code=rule.code,
                            message=rule.message,
                            cwe=rule.cwe,
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Зависимости — A06 Vulnerable and Outdated Components
# ---------------------------------------------------------------------------


async def run_dependency_check(project_path: str) -> list[RawFinding]:
    """Проверить зависимости на известные CVE через pip-audit."""
    findings: list[RawFinding] = []

    # Ищем requirements-файлы
    req_files: list[Path] = []
    root = Path(project_path)
    for pattern in ("requirements*.txt", "requirements/*.txt"):
        req_files.extend(root.rglob(pattern))

    if not req_files:
        # Нет requirements — пропускаем
        return findings

    for req_file in req_files:
        stdout, stderr, rc = await _run(
            ["pip-audit", "-r", str(req_file), "--format", "json", "--skip-editable"],
            cwd=project_path,
        )
        if not stdout.strip():
            continue
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            continue

        # pip-audit JSON schema: {"dependencies": [{"name", "version", "vulns": [{"id", "description", "fix_versions"}]}]}
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                vuln_id: str = vuln.get("id", "")
                desc: str = vuln.get("description", "")
                fix: list[str] = vuln.get("fix_versions", [])
                fix_str = ", ".join(fix) if fix else "no fix available"
                findings.append(
                    RawFinding(
                        owasp_category="A06",
                        owasp_title="Vulnerable and Outdated Components",
                        checker="pip-audit",
                        severity="high",
                        file_path=os.path.relpath(str(req_file), project_path),
                        line=None,
                        column=None,
                        code=vuln_id,
                        message=(
                            f"{dep.get('name')}=={dep.get('version')} has vulnerability {vuln_id}: "
                            f"{desc} (fix: {fix_str})"
                        ),
                        cwe=None,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


async def run_all(project_path: str) -> list[RawFinding]:
    """Запустить все чекеры параллельно и вернуть объединённый список находок."""
    results = await asyncio.gather(
        run_bandit_security(project_path),
        run_regex_security(project_path),
        run_dependency_check(project_path),
        return_exceptions=True,
    )
    findings: list[RawFinding] = []
    for result in results:
        if isinstance(result, list):
            findings.extend(result)
    return findings
