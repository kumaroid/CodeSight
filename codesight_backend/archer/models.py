from pydantic import BaseModel, Field
from typing import List, Optional


class ServiceDescription(BaseModel):
    name: str
    responsibility: str
    technologies: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    protocols: List[str] = Field(default_factory=list)
    datastore: Optional[str] = None


class ArchitectureInput(BaseModel):
    project_name: str
    business_context: str
    architecture_summary: str
    services: List[ServiceDescription] = Field(default_factory=list)
    known_issues: List[str] = Field(default_factory=list)
    quality_attributes: List[str] = Field(
        default_factory=lambda: [
            "scalability",
            "reliability",
            "security",
            "maintainability",
        ]
    )


class Recommendation(BaseModel):
    """Структурированная рекомендация"""

    title: str
    problem: str
    risk: str
    recommendation: str
    expected_effect: Optional[str] = None
    priority: str = "medium"  # high, medium, low


class RecommendationResponse(BaseModel):
    """Ответ с анализом архитектуры"""

    summary: str
    findings: List[dict]  # Предварительный анализ
    model_summary: str  # Резюме от модели
    recommendations: List[Recommendation]  # Структурированные рекомендации
    raw_model_output: str  # Оригинальный вывод модели
