FROM python:3.12-slim-bookworm AS build
WORKDIR /app
COPY requirements.txt ./
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache \
    pip install --no-cache-dir --upgrade pip && \
    pip wheel --wheel-dir=/wheels -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app app
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build /wheels /wheels
RUN --mount=type=cache,target=/root/.cache \
    pip install --no-cache-dir /wheels/*
COPY . .
RUN chown -R app:app /app
USER app
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["curl", "-f", "http://localhost:8080/health"]
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
