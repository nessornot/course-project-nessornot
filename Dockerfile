FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache \
    pip install --no-cache-dir --upgrade pip && \
    pip wheel --wheel-dir=/wheels -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl=7.88.1-10+deb12u5 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /wheels /wheels
RUN --mount=type=cache,target=/root/.cache \
    pip install --no-cache-dir /wheels/*

COPY . .
RUN chown -R app:app /app

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["curl", "-f", "http://localhost:8080/health"] || exit 1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
