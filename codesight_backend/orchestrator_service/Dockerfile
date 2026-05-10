FROM python:3.12-slim

WORKDIR /app

COPY codesight_backend/orchestrator_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY codesight_backend/orchestrator_service/ ./orchestrator_service/

CMD ["uvicorn", "orchestrator_service.main:app", "--host", "0.0.0.0", "--port", "8007"]
