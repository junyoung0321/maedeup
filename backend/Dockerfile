FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Test deps — baked into the image so `docker compose build` doesn't drop them.
# `maedeup-cr` stack uses these; prod deploys can drop this layer later if needed.
COPY requirements-dev.txt* ./
RUN if [ -f requirements-dev.txt ]; then pip install --no-cache-dir -r requirements-dev.txt; fi

COPY . .

EXPOSE 8000

CMD ["sh", "-ec", "python -c \"import asyncio; from app.db.session import init_db; asyncio.run(init_db())\" && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
