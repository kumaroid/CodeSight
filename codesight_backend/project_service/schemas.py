from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


# ---- запросы ----

class ProjectFromRepoRequest(BaseModel):
    """Тело запроса для загрузки проекта из URL репозитория."""
    repo_url: HttpUrl
    name: str | None = None  # если не задано — берётся из последнего сегмента URL


# ---- ответы ----

class ProjectResponse(BaseModel):
    id: str
    name: str
    source_type: Literal["zip", "git"]
    repo_url: str | None
    storage_path: str | None
    status: Literal["pending", "ready", "error"]
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
