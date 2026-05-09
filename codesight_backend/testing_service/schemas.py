from datetime import datetime

from pydantic import BaseModel


class FileCoverageOut(BaseModel):
    id: int
    file_path: str
    lines_total: int
    lines_covered: int
    lines_missing: int
    coverage_percent: float
    missing_lines: str | None  # JSON-строка с номерами строк

    model_config = {"from_attributes": True}


class TestResultOut(BaseModel):
    id: int
    node_id: str
    outcome: str
    duration_seconds: float | None
    longrepr: str | None

    model_config = {"from_attributes": True}


class TestRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    error_message: str | None

    # Метрики покрытия
    coverage_percent: float | None
    lines_total: int | None
    lines_covered: int | None
    lines_missing: int | None
    branches_total: int | None
    branches_covered: int | None
    branch_coverage_percent: float | None

    # Метрики тестов
    tests_total: int | None
    tests_passed: int | None
    tests_failed: int | None
    tests_error: int | None
    tests_skipped: int | None
    duration_seconds: float | None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestRunDetail(TestRunOut):
    file_coverages: list[FileCoverageOut] = []
    test_results: list[TestResultOut] = []


class TestRunListResponse(BaseModel):
    items: list[TestRunOut]
    total: int


class StartTestRunRequest(BaseModel):
    project_id: str
