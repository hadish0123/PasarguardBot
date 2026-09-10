FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    UV_CACHE_DIR=/root/.cache/uv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libffi-dev \
        libssl-dev \
        mariadb-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
# The Bot API migration changes the dependency graph; let uv refresh the lock
# during the image build instead of failing on a stale frozen lock file.
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/logs /app/sessions

ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="PasarguardBot" \
      org.opencontainers.image.description="PasarguardBot Telegram management bot" \
      org.opencontainers.image.source="https://github.com/hadish0123/PasarguardBot" \
      org.opencontainers.image.url="https://github.com/AmirKenzo/PasarguardBot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uv", "run", "main.py"]
