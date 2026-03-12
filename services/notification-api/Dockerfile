# -----------------------------
# Stage 1: builder (wheels)
# -----------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
  && rm -rf /var/lib/apt/lists/*

COPY services/notification-api/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
  && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# -----------------------------
# Stage 2: runtime (minimal)
# -----------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
  && rm -rf /wheels

COPY services/shared ./services/shared
COPY services/notification-api/src ./src

USER app

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
