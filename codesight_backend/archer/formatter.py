import re
from typing import Optional
from pydantic import BaseModel
from .models import Recommendation


class FormattedOutput(BaseModel):
    """Форматированный вывод модели"""

    summary: str
    recommendations: list[Recommendation]
    raw_output: str


class ModelOutputFormatter:
    """Форматтер для парсинга и структурирования вывода GigaChat"""

    @staticmethod
    def parse_priority(text: str) -> str:
        """Извлекает приоритет из текста"""
        priorities = {
            "high": ["высок", "критич", "срочн"],
            "medium": ["средн", "важн"],
            "low": ["низк", "опцион"],
        }
        text_lower = text.lower()
        for priority, keywords in priorities.items():
            if any(kw in text_lower for kw in keywords):
                return priority
        return "medium"

    @staticmethod
    def extract_summary(text: str) -> str:
        """Извлекает резюме (первый абзац)"""
        paragraphs = text.split("\n\n")
        if paragraphs:
            summary = paragraphs[0].strip()
            # Ограничиваем длину резюме
            if len(summary) > 500:
                sentences = summary.split(". ")
                truncated = ""
                for sent in sentences:
                    if len(truncated) + len(sent) < 500:
                        truncated += sent + ". "
                    else:
                        break
                return truncated.strip()
            return summary
        return ""

    @staticmethod
    def extract_recommendations(text: str) -> list[Recommendation]:
        """Парсит рекомендации из текста модели"""
        recommendations = []

        # Паттерн для поиска блоков рекомендаций
        # Ищет строки, начинающиеся с числа, дефиса или звёздочки
        blocks = re.split(r"(?:^|\n)(?:\d+\.|[-*])\s+", text, flags=re.MULTILINE)

        for block in blocks[
            1:
        ]:  # Пропускаем первый элемент (текст до первой рекомендации)
            if not block.strip():
                continue

            lines = block.strip().split("\n")
            if not lines:
                continue

            recommendation = ModelOutputFormatter._parse_recommendation_block(lines)
            if recommendation:
                recommendations.append(recommendation)

        return recommendations

    @staticmethod
    def _parse_recommendation_block(lines: list[str]) -> Optional[Recommendation]:
        """Парсит один блок рекомендации"""
        if not lines:
            return None

        title = lines[0].strip()
        problem = ""
        risk = ""
        recommendation_text = ""
        expected_effect = ""
        priority = "medium"

        current_section = None
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            line_lower = line.lower()

            # Определяем раздел
            if any(
                kw in line_lower for kw in ["проблем", "проблема", "issue", "problem"]
            ):
                current_section = "problem"
                problem = line.replace("Проблема:", "").replace("Проблем:", "").strip()
            elif any(kw in line_lower for kw in ["риск", "risk"]):
                current_section = "risk"
                risk = line.replace("Риск:", "").replace("Risk:", "").strip()
            elif any(
                kw in line_lower
                for kw in ["рекомендац", "рекомендация", "recommendation"]
            ):
                current_section = "recommendation"
                recommendation_text = (
                    line.replace("Рекомендация:", "")
                    .replace("Recommendation:", "")
                    .strip()
                )
            elif any(kw in line_lower for kw in ["эффект", "эффекты", "effect"]):
                current_section = "effect"
                expected_effect = (
                    line.replace("Ожидаемый эффект:", "")
                    .replace("Expected effect:", "")
                    .strip()
                )
            elif any(kw in line_lower for kw in ["приоритет", "priority"]):
                priority = ModelOutputFormatter.parse_priority(line)
            elif current_section == "problem":
                problem += " " + line
            elif current_section == "risk":
                risk += " " + line
            elif current_section == "recommendation":
                recommendation_text += " " + line
            elif current_section == "effect":
                expected_effect += " " + line

        # Если основной текст - используем его как всё сразу
        if not problem and not risk:
            full_text = "\n".join(lines[1:])
            # Пытаемся разделить по ключевым словам
            if "проблем" in full_text.lower() or "риск" in full_text.lower():
                pass  # Уже обработано выше
            else:
                problem = full_text[:200]  # Первые 200 символов как проблема

        return Recommendation(
            title=title,
            problem=problem.strip(),
            risk=risk.strip(),
            recommendation=recommendation_text.strip(),
            expected_effect=expected_effect.strip() if expected_effect else None,
            priority=priority,
        )

    @classmethod
    def format(cls, raw_output: str) -> FormattedOutput:
        """Форматирует полный вывод модели"""
        summary = cls.extract_summary(raw_output)
        recommendations = cls.extract_recommendations(raw_output)

        return FormattedOutput(
            summary=summary,
            recommendations=recommendations,
            raw_output=raw_output,
        )
