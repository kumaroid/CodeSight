FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    uv sync --frozen --no-dev

COPY codesight_backend/auth_service ./codesight_backend/auth_service

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "codesight_backend.auth_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
