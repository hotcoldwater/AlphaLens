FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALPHALENS_DATABASE_PATH=/var/data/alphalens.db \
    ALPHALENS_MARKET_DATA_PATH=/var/data/market_data

COPY requirements.txt ./
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY services ./services

EXPOSE 8000

CMD ["sh", "-c", "uvicorn services.api.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
