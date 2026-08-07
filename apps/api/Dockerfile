# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# FinManager API — FastAPI + SQLAlchemy 2.0 + Celery
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Lisbon

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh \
 && mkdir -p /var/lib/finmanager/storage

# ---------------------------------------------------------------------------
# dev — adds the tooling needed by `make check`; source is bind-mounted
# ---------------------------------------------------------------------------
FROM base AS dev
RUN pip install -r requirements-dev.txt
COPY . /app
CMD ["/app/docker-entrypoint.sh", "api-dev"]

# ---------------------------------------------------------------------------
# runtime — non-root, no dev tooling
# ---------------------------------------------------------------------------
FROM base AS runtime
COPY . /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin finmanager \
 && chown -R finmanager:finmanager /app /var/lib/finmanager
USER finmanager
EXPOSE 8000
CMD ["/app/docker-entrypoint.sh", "api"]
