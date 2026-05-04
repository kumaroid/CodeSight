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
