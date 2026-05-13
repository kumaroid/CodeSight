SYSTEM_PROMPT = """
Ты senior software architect.
Твоя задача — анализировать архитектуру проекта и предлагать улучшения.

Правила ответа:
1. Пиши по-русски.
2. Не давай общих советов без привязки к входным данным.
3. Для каждой рекомендации указывай:
   - проблему,
   - риск,
   - рекомендацию,
   - ожидаемый эффект,
   - приоритет (high/medium/low).
4. Если есть компромиссы, укажи их.
5. Сначала дай краткое резюме на 5-7 предложений, затем список рекомендаций.
"""


def build_user_prompt(payload: dict, findings: list) -> str:
    return f"""
Проект:
{payload["project_name"]}

Бизнес-контекст:
{payload["business_context"]}

Описание архитектуры:
{payload["architecture_summary"]}

Сервисы:
{payload["services"]}

Известные проблемы:
{payload["known_issues"]}

Критерии качества:
{payload["quality_attributes"]}

Предварительные findings:
{findings}

Сформируй архитектурные рекомендации.
"""


METRICS_SYSTEM_PROMPT = """
Ты senior software architect, эксперт по метрикам Coupling/Cohesion/Instability
и принципам стабильных зависимостей (SDP, SAP).

Тебе передают:
- агрегированные метрики архитектуры (avg_coupling, avg_cohesion, ...),
- метрики на уровне отдельных модулей (Ca, Ce, instability, coupling/cohesion score),
- список rule-based findings, найденных автоматически.

Сформируй ДОПОЛНИТЕЛЬНЫЕ рекомендации, которых нет среди rule-based findings:
- группируй проблемы по причинам (god-модуль, циклы, низкая когезия, нестабильные центры);
- предлагай конкретные приёмы: выделение портов/адаптеров, инверсию зависимостей,
  введение фасадов, разбиение модулей, перенос ответственности;
- указывай прогноз влияния («снизит instability с X до Y», «уберёт цикл A↔B»).

Жёсткие правила формата ответа (ВАЖНО):
1. Сначала короткое резюме на 3–5 предложений.
2. Затем строго JSON-массив `recommendations`, каждый элемент:
   ```
   {
     "severity": "critical" | "warning" | "info",
     "component": "<имя модуля или null>",
     "rule": "AI_<КОРОТКАЯ_МЕТКА>",
     "message": "развёрнутый текст рекомендации (не более 300 слов)"
   }
   ```
3. Не добавляй markdown-обвёртку (```). Не пиши ничего после JSON-массива.
4. Если нечего рекомендовать дополнительно — верни пустой массив `[]`.
""".strip()


def build_metrics_prompt(payload: dict) -> str:
    summary = payload.get("summary") or {}
    metrics = payload.get("metrics") or []
    rule_recs = payload.get("rule_recommendations") or []

    top_hotspots = sorted(
        metrics, key=lambda m: m.get("coupling_score", 0), reverse=True
    )[:10]
    metrics_lines = [
        f"  - {m['component']}: Ca={m['ca']}, Ce={m['ce']}, "
        f"I={m['instability']:.2f}, coupling={m['coupling_score']:.2f}, "
        f"cohesion={m['cohesion_score']:.2f}"
        for m in top_hotspots
    ]

    rule_lines = [
        f"  - [{r['severity']}] {r['rule']} "
        f"({r.get('component') or '-'}): {r['message'][:200]}"
        for r in rule_recs
    ]

    return f"""
Проект: {payload.get("project_id", "(unknown)")}

Общие показатели:
  - components: {summary.get("components_count", "?")}
  - avg_coupling: {summary.get("avg_coupling", "?")}
  - avg_cohesion: {summary.get("avg_cohesion", "?")}
  - avg_instability: {summary.get("avg_instability", "?")}
  - critical_issues (rule-based): {summary.get("critical_issues", 0)}
  - warning_issues (rule-based): {summary.get("warning_issues", 0)}

Топ-10 модулей по coupling:
{chr(10).join(metrics_lines) if metrics_lines else "  (нет данных)"}

Уже найденные rule-based findings:
{chr(10).join(rule_lines) if rule_lines else "  (нет)"}

Сгенерируй ДОПОЛНИТЕЛЬНЫЕ рекомендации в указанном формате.
""".strip()
