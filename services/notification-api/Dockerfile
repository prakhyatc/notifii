# -----------------------------
# Stage 1: builder (wheels)
# -----------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps (kept minimal). curl is not needed in builder.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels so runtime image doesn't need compilers
RUN pip install --no-cache-dir --upgrade pip \
  && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# -----------------------------
# Stage 2: runtime (minimal)
# -----------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# Install runtime dependencies from wheels only
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
  && rm -rf /wheels

# Copy application code
COPY src ./src

# Switch to non-root
USER app

EXPOSE 8000

# Run uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
