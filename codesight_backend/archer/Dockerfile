FROM docker.io/library/python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY codesight_backend/archer/requirements.txt ./req.txt
RUN env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    uv pip install --system -r req.txt

COPY codesight_backend/archer ./codesight_backend/archer

ENV PYTHONPATH=/app

EXPOSE 8009

CMD ["uvicorn", "codesight_backend.archer.main:app", "--host", "0.0.0.0", "--port", "8009"]
