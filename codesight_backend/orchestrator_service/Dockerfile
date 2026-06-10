FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY codesight_backend/orchestrator_service/requirements.txt ./requirements.txt
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    uv pip install --system -r requirements.txt

COPY codesight_backend/orchestrator_service/ ./orchestrator_service/

CMD ["uvicorn", "orchestrator_service.main:app", "--host", "0.0.0.0", "--port", "8007"]
