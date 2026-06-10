FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY codesight_backend/kafka_common ./codesight_backend/kafka_common
COPY codesight_backend/arch_service/requirements.txt ./req.txt
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    uv pip install --system -r req.txt

COPY codesight_backend/arch_service ./codesight_backend/arch_service

ENV PYTHONPATH=/app

EXPOSE 8006

CMD ["uvicorn", "codesight_backend.arch_service.main:app", "--host", "0.0.0.0", "--port", "8006"]
