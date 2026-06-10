"""Archer — LLM-агент для архитектурных рекомендаций.

Endpoints:

- `POST /analyze` — ручной режим: пользователь описывает архитектуру руками
  (ServiceDescription и т.п.), модель формирует рекомендации.
- `POST /analyze-metrics` — автоматический режим: сюда `arch_service`
  присылает рассчитанные метрики Coupling/Cohesion + rule-based findings,
  archer возвращает дополнительные подсказки (best-effort через GigaChat,
  с fallback на эвристику, если LLM недоступен).
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .formatter import ModelOutputFormatter
from .gigachat_client import GigaChatArchitectureAdvisor
from .models import (
    AIRecommendation,
    ArchitectureInput,
    ArchMetricsInput,
    ArchMetricsResponse,
    RecommendationResponse,
)
from .promts import METRICS_SYSTEM_PROMPT, build_metrics_prompt, build_user_prompt
from .rules import analyze_architecture

logger = logging.getLogger(__name__)


def _load_env_file() -> None:
    """Подхватывает archer/.env, если переменные ещё не заданы."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


app = FastAPI(
    title="Archer — AI architecture advisor",
    version="1.0.0",
    description=(
        "AI-агент для архитектурных рекомендаций. Принимает либо ручное "
        "описание архитектуры, либо вычисленные Coupling/Cohesion-метрики."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


advisor = GigaChatArchitectureAdvisor()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "archer",
        "llm_available": advisor.is_available(),
    }


# --------------------------------------------------------------------------- #
# /analyze — ручной режим (как было раньше)
# --------------------------------------------------------------------------- #


@app.post("/analyze", response_model=RecommendationResponse)
def analyze(data: ArchitectureInput) -> RecommendationResponse:
    findings = analyze_architecture(data)

    payload = {
        "project_name": data.project_name,
        "business_context": data.business_context,
        "architecture_summary": data.architecture_summary,
        "services": [svc.model_dump() for svc in data.services],
        "known_issues": data.known_issues,
        "quality_attributes": data.quality_attributes,
    }

    prompt = build_user_prompt(payload, findings)
    llm_output = advisor.recommend(prompt)
    if llm_output is None:
        # LLM недоступен — собираем псевдо-вывод из findings, чтобы фронт
        # получил предсказуемую структуру
        llm_output = _fallback_text_from_findings(findings)

    formatted = ModelOutputFormatter.format(llm_output)

    return RecommendationResponse(
        summary="Архитектурный анализ выполнен",
        findings=findings,
        model_summary=formatted.summary,
        recommendations=formatted.recommendations,
        raw_model_output=formatted.raw_output,
    )


# --------------------------------------------------------------------------- #
# /analyze-metrics — автоматический режим (вызывается arch_service)
# --------------------------------------------------------------------------- #


@app.post("/analyze-metrics", response_model=ArchMetricsResponse)
def analyze_metrics(data: ArchMetricsInput) -> ArchMetricsResponse:
    """Принимает метрики Coupling/Cohesion + rule-based findings, возвращает AI-рекомендации.

    Никогда не падает: при недоступном LLM возвращает эвристический fallback.
    """
    payload = data.model_dump()

    llm_output: str | None = None
    if advisor.is_available():
        prompt = METRICS_SYSTEM_PROMPT + "\n\n" + build_metrics_prompt(payload)
        llm_output = advisor.recommend(prompt)

    if llm_output:
        summary_text, recs = _parse_metrics_response(llm_output)
        if recs:
            return ArchMetricsResponse(
                summary=summary_text,
                recommendations=recs,
                source="gigachat",
            )

    # Fallback: формируем эвристические подсказки прямо из метрик
    summary_text, recs = _fallback_metrics_recommendations(data)
    return ArchMetricsResponse(
        summary=summary_text,
        recommendations=recs,
        source="fallback",
    )


# --------------------------------------------------------------------------- #
# Парсинг ответа модели и fallback
# --------------------------------------------------------------------------- #


_JSON_ARRAY_RE = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


def _parse_metrics_response(text: str) -> tuple[str, list[AIRecommendation]]:
    """Ищет в ответе модели JSON-массив рекомендаций.

    Если ничего не нашлось — возвращает пустой список (вызывающий код
    переключится на fallback).
    """
    match = _JSON_ARRAY_RE.search(text)
    summary = text
    recs: list[AIRecommendation] = []
    if match:
        summary = text[: match.start()].strip()
        json_blob = match.group(0)
        try:
            raw_items = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            logger.warning("Не удалось распарсить JSON из ответа LLM: %s", exc)
            return summary or text.strip(), []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            msg = (item.get("message") or "").strip()
            if not msg:
                continue
            recs.append(
                AIRecommendation(
                    severity=_normalize_severity(item.get("severity")),
                    component=item.get("component"),
                    rule=str(item.get("rule") or "AI_HINT"),
                    message=msg[:2000],
                )
            )
    return (summary or text.strip())[:1500], recs


def _normalize_severity(value: object) -> str:
    if isinstance(value, str):
        v = value.lower().strip()
        if v in ("critical", "high"):
            return "critical"
        if v in ("warning", "medium"):
            return "warning"
        if v in ("info", "low"):
            return "info"
    return "info"


def _fallback_text_from_findings(findings: list[dict]) -> str:
    if not findings:
        return "Архитектура выглядит в норме — критичных проблем не найдено."
    parts = ["Резюме: автоматический анализ нашёл следующие проблемные места.\n"]
    for f in findings:
        parts.append(
            f"- {f.get('title')}: {f.get('risk')}. Рекомендуется: {f.get('recommendation')}."
        )
    return "\n".join(parts)


def _fallback_metrics_recommendations(
    data: ArchMetricsInput,
) -> tuple[str, list[AIRecommendation]]:
    """Эвристические подсказки, когда GigaChat недоступен.

    Они опираются на агрегаты + топ-3 проблемных модуля. Это НЕ дублирует
    rule-based рекомендации arch_service — фокус на «как переделать», а не
    «что нашли».
    """
    summary = data.summary or {}
    avg_coupling = float(summary.get("avg_coupling", 0))
    # avg_cohesion может быть None (когда у всех модулей нет наблюдаемых
    # соседей или все они изолированы) — тогда правила про cohesion пропускаем.
    raw_avg_cohesion = summary.get("avg_cohesion")
    avg_cohesion: float | None = (
        float(raw_avg_cohesion) if isinstance(raw_avg_cohesion, (int, float)) else None
    )
    components_n = int(summary.get("components_count", 0))

    recs: list[AIRecommendation] = []

    hotspots = sorted(data.metrics, key=lambda m: m.coupling_score, reverse=True)[:3]
    for m in hotspots:
        if m.coupling_score >= 0.6:
            recs.append(
                AIRecommendation(
                    severity="warning" if m.coupling_score < 0.85 else "critical",
                    component=m.component,
                    rule="AI_EXTRACT_FACADE",
                    message=(
                        f"Модуль '{m.component}' — кандидат на декомпозицию: "
                        f"Ca={m.ca}, Ce={m.ce}, coupling={m.coupling_score:.2f}. "
                        "Выделите отдельный фасад (façade) для стабильного публичного API и "
                        "перенесите внутренние зависимости за него. Если у модуля высокий Ce, "
                        "разделите его по доменам ответственности; если высокий Ca — введите "
                        "интерфейсы (Dependency Inversion), чтобы клиенты зависели от абстракций."
                    ),
                )
            )

    cyclic = [m for m in data.metrics if m.ca > 0 and m.ce > 0 and m.instability > 0.4]
    if cyclic and any(
        r.rule == "CIRCULAR_DEPENDENCY" for r in data.rule_recommendations
    ):
        recs.append(
            AIRecommendation(
                severity="critical",
                component=None,
                rule="AI_BREAK_CYCLES",
                message=(
                    "Циклические зависимости найдены автоматически. Универсальный приём — "
                    "перенести общий код в третий модуль-«core», от которого зависят оба "
                    "конца цикла, либо инвертировать одну из связей через абстрактный "
                    "интерфейс (Dependency Inversion). Циклы делают сборку и тестирование "
                    "невозможными по слоям и блокируют независимый деплой компонентов."
                ),
            )
        )

    if components_n >= 4 and avg_cohesion is not None and avg_cohesion < 0.5:
        recs.append(
            AIRecommendation(
                severity="warning",
                component=None,
                rule="AI_REGROUP_PACKAGES",
                message=(
                    f"Средняя cohesion {avg_cohesion:.2f} — модули часто общаются «через границы» "
                    "своих пакетов. Это сигнал к перегруппировке: сложите вместе модули, "
                    "которые меняются вместе и зовут друг друга, и отделите те, что используются "
                    "редко (Common Closure Principle, CCP)."
                ),
            )
        )

    if components_n >= 4 and avg_coupling > 0.5:
        recs.append(
            AIRecommendation(
                severity="warning",
                component=None,
                rule="AI_INTRODUCE_LAYERS",
                message=(
                    f"Средний coupling {avg_coupling:.2f} высокий. Введите явные слои "
                    "(domain → application → infrastructure) с правилом «зависимости направлены "
                    "только внутрь». Это уменьшит средний Ce у инфраструктурных модулей и "
                    "сделает доменные модули свободными от deps."
                ),
            )
        )

    if not recs:
        recs.append(
            AIRecommendation(
                severity="info",
                component=None,
                rule="AI_OK",
                message=(
                    "Текущая архитектура выглядит сбалансированной по метрикам Coupling и "
                    "Cohesion. Продолжайте следить за ростом Ce у центральных модулей и "
                    "избегайте появления циклов."
                ),
            )
        )

    cohesion_part = (
        f"средняя cohesion={avg_cohesion:.2f}"
        if avg_cohesion is not None
        else "средняя cohesion=n/a"
    )
    summary_text = (
        f"Архитектура: {components_n} модулей, средний coupling={avg_coupling:.2f}, "
        f"{cohesion_part}. "
        "GigaChat недоступен — использован эвристический режим: "
        f"подготовлено {len(recs)} дополнительных подсказок поверх rule-based findings."
    )
    return summary_text, recs
