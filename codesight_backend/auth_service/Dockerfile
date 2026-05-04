FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install only runtime dependencieuv s (skip dev tools)
RUN uv sync --frozen --no-dev

# Copy application source
COPY codesight_backend/auth_service ./codesight_backend/auth_service

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "codesight_backend.auth_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
