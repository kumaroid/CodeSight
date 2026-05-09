from datetime import datetime

from pydantic import BaseModel


class IssueOut(BaseModel):
    id: int
    tool: str
    severity: str
    file_path: str
    line: int | None
    column: int | None
    code: str | None
    message: str

    model_config = {"from_attributes": True}


class AnalysisRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunDetail(AnalysisRunOut):
    issues: list[IssueOut] = []


class AnalysisRunListResponse(BaseModel):
    items: list[AnalysisRunOut]
    total: int


class StartAnalysisRequest(BaseModel):
    project_id: str
