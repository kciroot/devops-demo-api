# syntax=docker/dockerfile:1

# ---- Stage 1: build the dependencies -------------------------------------
FROM python:3.13-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: minimal runtime image --------------------------------------
FROM python:3.13-slim

LABEL org.opencontainers.image.title="tasks-api" \
      org.opencontainers.image.description="DevOps demo: REST API with SQLite" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/tasks.db

# Apply OS security patches, then create an unprivileged user.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app \
 && mkdir -p /data \
 && chown app:app /data

COPY --from=builder /install /usr/local
WORKDIR /srv
COPY app ./app
COPY wsgi.py .

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

USER 10001
EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

# One worker because SQLite is a single file; threads handle concurrency.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "--worker-tmp-dir", "/tmp", "wsgi:app"]
