# ==========================================
# Stage 1: Build & Dependency Resolution
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system compilation tools if needed for native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Pre-download SentenceTransformer model to avoid cold startup latency in production
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ==========================================
# Stage 2: Production Final Image
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies for postgres client & curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security best practices
RUN groupadd -g 999 appuser && \
    useradd -r -u 999 -g appuser appuser

# Copy installed python packages & downloaded HuggingFace models from builder
COPY --from=builder /root/.local /home/appuser/.local
COPY --from=builder /root/.cache /home/appuser/.cache

# Copy application source code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY pyproject.toml .
COPY README.md .

# Permissions and environment configuration
RUN chown -R appuser:appuser /app /home/appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
