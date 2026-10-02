# media-studio 云端镜像：网关/分析引擎/MCP 三服务共用
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/

RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY studio ./studio

ENV VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    STUDIO_DATA_DIR=/data

EXPOSE 8100 8200

CMD ["uvicorn", "studio.gateway.app:app", "--host", "0.0.0.0", "--port", "8200"]
