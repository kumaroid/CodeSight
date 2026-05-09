from datetime import datetime

from pydantic import BaseModel


class SecurityFindingOut(BaseModel):
    id: int
    owasp_category: str
    owasp_title: str
    checker: str
    severity: str
    file_path: str
    line: int | None
    column: int | None
    code: str | None
    message: str
    cwe: str | None

    model_config = {"from_attributes": True}


class SecurityScanOut(BaseModel):
    id: str
    project_id: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SecurityScanDetail(SecurityScanOut):
    findings: list[SecurityFindingOut] = []


class SecurityScanListResponse(BaseModel):
    items: list[SecurityScanOut]
    total: int


class StartSecurityScanRequest(BaseModel):
    project_id: str
