from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .schemas import ProjectFromRepoRequest, ProjectListResponse, ProjectResponse
from .service import (
    delete_project,
    get_project,
    list_projects,
    upload_repo_project,
    upload_zip_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "/upload/zip",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить проект из ZIP-архива",
)
async def upload_zip(
    file: UploadFile = File(..., description="ZIP-архив с исходным кодом проекта"),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Принимает ZIP-архив, распаковывает его во временное хранилище
    и возвращает метаданные созданного проекта.
    """
    project = await upload_zip_project(file, db)
    return ProjectResponse.model_validate(project)


@router.post(
    "/upload/repo",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить проект из URL репозитория",
)
async def upload_repo(
    body: ProjectFromRepoRequest,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Принимает URL публичного репозитория (GitHub и другие),
    скачивает/клонирует его и возвращает метаданные проекта.
    """
    project = await upload_repo_project(
        repo_url=str(body.repo_url),
        name=body.name,
        db=db,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "/",
    response_model=ProjectListResponse,
    summary="Список всех проектов",
)
async def get_projects(
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    projects = await list_projects(db)
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=len(projects),
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Получить проект по ID",
)
async def get_project_by_id(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await get_project(project_id, db)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить проект",
)
async def remove_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_project(project_id, db)
