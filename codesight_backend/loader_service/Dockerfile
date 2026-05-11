FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY codesight_backend/loader_service/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY codesight_backend/loader_service ./codesight_backend/loader_service

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "codesight_backend.loader_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
