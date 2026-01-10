# -------- builder --------
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
  && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# -------- runtime --------
FROM python:3.11-slim AS runtime
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
  && rm -rf /wheels

COPY src ./src
USER app

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.worker"]
