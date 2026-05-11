FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    valgrind \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY codesight_backend/kafka_common ./codesight_backend/kafka_common
COPY codesight_backend/dast_service/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY codesight_backend/dast_service ./codesight_backend/dast_service

ENV PYTHONPATH=/app

EXPOSE 8008

CMD ["uvicorn", "codesight_backend.dast_service.main:app", "--host", "0.0.0.0", "--port", "8008"]
