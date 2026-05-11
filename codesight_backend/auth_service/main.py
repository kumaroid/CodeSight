from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .router import router

BASE_DIR = Path(__file__).resolve().parents[2]  # корень репо
FRONTEND_DIR = BASE_DIR / "codesight_frontend"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="CodeSight Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)

if FRONTEND_DIR.is_dir():
    app.mount(
        "/codesight_frontend",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="codesight_frontend",
    )


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    # В контейнере frontend может не монтироваться.
    homepage = FRONTEND_DIR / "homepage.html"
    if homepage.is_file():
        html = homepage.read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    return HTMLResponse(content="CodeSight Auth Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
