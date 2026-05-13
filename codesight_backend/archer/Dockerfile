FROM docker.io/library/python:3.12-slim

WORKDIR /app

COPY codesight_backend/archer/requirements.txt ./req.txt
RUN pip install --no-cache-dir -r req.txt

COPY codesight_backend/archer ./codesight_backend/archer

ENV PYTHONPATH=/app

EXPOSE 8009

CMD ["uvicorn", "codesight_backend.archer.main:app", "--host", "0.0.0.0", "--port", "8009"]
