from datetime import datetime

from pydantic import BaseModel


class ComponentMetricOut(BaseModel):
    id: int
    component: str
    ca: int
    ce: int
    instability: float
    coupling_score: float
    cohesion_score: float

    model_config = {"from_attributes": True}


class ArchRecommendationOut(BaseModel):
    id: int
    severity: str
    component: str | None
    rule: str
    message: str

    model_config = {"from_attributes": True}


class ArchRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArchRunDetail(ArchRunOut):
    metrics: list[ComponentMetricOut] = []
    recommendations: list[ArchRecommendationOut] = []
    summary: dict | None = None


class ArchRunListResponse(BaseModel):
    items: list[ArchRunOut]
    total: int


class StartArchRequest(BaseModel):
    project_id: str
    plantuml: str  # raw PlantUML diagram text
