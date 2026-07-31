FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sunset Telegram Bot"
LABEL org.opencontainers.image.description="Telegram bot worker for Timeweb Cloud"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates fonts-dejavu-core fonts-inter fonts-lato fonts-ebgaramond \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/generated /app/data

CMD ["python", "run_bot.py"]
