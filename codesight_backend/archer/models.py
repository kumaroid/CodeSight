from typing import List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Старый ручной режим: высокоуровневое описание архитектуры
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Новый автоматический режим: на вход — метрики от arch_service
# --------------------------------------------------------------------------- #


class ComponentMetricIn(BaseModel):
    component: str
    ca: int
    ce: int
    instability: float
    coupling_score: float
    # None — изолированный модуль (нет соседей в графе), cohesion не определена.
    cohesion_score: Optional[float] = None


class RuleRecommendationIn(BaseModel):
    severity: str
    component: Optional[str] = None
    rule: str
    message: str


class ArchMetricsInput(BaseModel):
    project_id: str
    summary: dict = Field(default_factory=dict)
    metrics: List[ComponentMetricIn] = Field(default_factory=list)
    rule_recommendations: List[RuleRecommendationIn] = Field(default_factory=list)


class AIRecommendation(BaseModel):
    severity: str = "info"
    component: Optional[str] = None
    rule: str = "AI_HINT"
    message: str


class ArchMetricsResponse(BaseModel):
    summary: str
    recommendations: List[AIRecommendation]
    source: str  # "gigachat" или "fallback"


# --------------------------------------------------------------------------- #
# Старая структура ответа (manual /analyze)
# --------------------------------------------------------------------------- #


class Recommendation(BaseModel):
    title: str
    problem: str
    risk: str
    recommendation: str
    expected_effect: Optional[str] = None
    priority: str = "medium"


class RecommendationResponse(BaseModel):
    summary: str
    findings: List[dict]
    model_summary: str
    recommendations: List[Recommendation]
    raw_model_output: str
