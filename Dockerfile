FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[dev]"

COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY config/ ./config/

ENV PYTHONPATH=/app/src
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
