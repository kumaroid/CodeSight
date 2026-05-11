FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY codesight_backend/kafka_common ./codesight_backend/kafka_common
COPY codesight_backend/sast_service/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY codesight_backend/sast_service ./codesight_backend/sast_service

ENV PYTHONPATH=/app

EXPOSE 8003

CMD ["uvicorn", "codesight_backend.sast_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
