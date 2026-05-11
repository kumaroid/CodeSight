FROM python:3.12-slim

WORKDIR /app

COPY codesight_backend/kafka_common ./codesight_backend/kafka_common
COPY codesight_backend/testing_service/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY codesight_backend/testing_service ./codesight_backend/testing_service

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["uvicorn", "codesight_backend.testing_service.main:app", "--host", "0.0.0.0", "--port", "8004"]
