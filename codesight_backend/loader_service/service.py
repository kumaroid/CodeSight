from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

import httpx
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Project


def _project_storage_path(project_id: str) -> Path:
    return Path(settings.storage_dir) / project_id


def _ensure_storage_root() -> None:
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)


async def upload_zip_project(
    file: UploadFile,
    db: AsyncSession,
) -> Project:
    if file.content_type not in ("application/zip", "application/x-zip-compressed"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Файл должен быть ZIP-архивом.",
        )

    content = await file.read()
    if len(content) > settings.max_zip_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Размер архива превышает допустимый ({settings.max_zip_size_bytes} байт).",
        )

    project_id = str(uuid.uuid4())
    project_name = Path(file.filename or "project").stem
    storage_path = _project_storage_path(project_id)
    _ensure_storage_root()
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for member in zf.namelist():
                if ".." in Path(member).parts:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Архив содержит небезопасные пути (path traversal).",
                    )
            zf.extractall(storage_path)
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не является корректным ZIP-архивом",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    project = Project(
        id=project_id,
        name=project_name,
        source_type="zip",
        storage_path=str(storage_path),
        status="ready",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def upload_repo_project(
    repo_url: str,
    name: str | None,
    db: AsyncSession,
) -> Project:
    project_id = str(uuid.uuid4())
    storage_path = _project_storage_path(project_id)
    _ensure_storage_root()
    derived_name = name or repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    project = Project(
        id=project_id,
        name=derived_name,
        source_type="git",
        repo_url=repo_url,
        storage_path=str(storage_path),
        status="pending",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    try:
        await _clone_repo(repo_url, storage_path)
        project.status = "ready"
    except Exception as exc:
        project.status = "error"
        project.error_message = str(exc)

    await db.commit()
    await db.refresh(project)
    return project


async def _clone_repo(repo_url: str, dest: Path) -> None:
    if "github.com" in repo_url:
        await _clone_github_via_api(repo_url, dest)
    else:
        await _clone_via_git(repo_url, dest)


async def _clone_github_via_api(repo_url: str, dest: Path) -> None:
    clean = repo_url.rstrip("/").removesuffix(".git")
    for branch in ("main", "master"):
        archive_url = f"{clean}/archive/refs/heads/{branch}.zip"
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            response = await client.get(archive_url)
            if response.status_code == 200:
                _unzip_bytes(response.content, dest)
                return
    raise RuntimeError(f"Не удалось скачать репозиторий {repo_url}")


def _unzip_bytes(content: bytes, dest: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(dest)
    finally:
        tmp_path.unlink(missing_ok=True)


async def _clone_via_git(repo_url: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "git",
        "clone",
        "--depth",
        "1",
        repo_url,
        str(dest),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"git clone завершился с ошибкой:\n{stderr.decode(errors='replace')}"
        )


async def get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Проект {project_id!r} не найден.",
        )
    return project


async def list_projects(db: AsyncSession) -> list[Project]:
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def delete_project(project_id: str, db: AsyncSession) -> None:
    project = await get_project(project_id, db)
    if project.storage_path:
        shutil.rmtree(project.storage_path, ignore_errors=True)
    await db.delete(project)
    await db.commit()
