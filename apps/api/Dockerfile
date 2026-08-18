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

# tesseract (+ Portuguese data) and zbar back the local OCR and fiscal-QR engines.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl tzdata tesseract-ocr tesseract-ocr-por libzbar0 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# The app user is created in *base* so dev and runtime agree on uid/gid: both
# stages mount the same `storage-data` volume, and a document written by one has
# to stay writable by the other. `2775` makes the group sticky, so a file created
# by the root dev container is still group-writable by the runtime user.
RUN chmod +x /app/docker-entrypoint.sh \
 && groupadd --gid 10001 finmanager \
 && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin finmanager \
 && mkdir -p /var/lib/finmanager/storage \
 && chown -R root:finmanager /var/lib/finmanager \
 && chmod -R 2775 /var/lib/finmanager

# ---------------------------------------------------------------------------
# dev — adds the tooling needed by `make check`; source is bind-mounted
# ---------------------------------------------------------------------------
FROM base AS dev
RUN pip install -r requirements-dev.txt
COPY . /app
CMD ["/app/docker-entrypoint.sh", "api-dev"]

# ---------------------------------------------------------------------------
# runtime — no dev tooling. The container starts as root only long enough to
# reconcile the storage volume's ownership; the entrypoint drops to `finmanager`
# before anything that serves a request runs (ADR-0024).
# ---------------------------------------------------------------------------
FROM base AS runtime
COPY . /app
RUN chown -R finmanager:finmanager /app
EXPOSE 8000
CMD ["/app/docker-entrypoint.sh", "api"]
