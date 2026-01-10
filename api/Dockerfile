# ================================
# Stage 1: Builder
# ================================
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY api/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# ================================
# Stage 2: Runtime
# ================================
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Add local bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Create directory structure
RUN mkdir -p /api /training

# Copy application files (preserve structure)
COPY api/main.py /api/
COPY api/schemas.py /api/
COPY api/forecaster.py /api/
COPY api/feature_engineer.py /api/
COPY api/model_loader.py /api/
COPY api/monitoring.py /api/
COPY api/predict_and_validate.py /api/
COPY api/prediction_tracker.py /api/

# Copy monitoring components from training
COPY training/metrics_collector.py /training/
COPY training/alert_manager.py /training/
COPY training/health_checks.py /training/

# Copy drift detector from monitoring
RUN mkdir -p /monitoring
COPY monitoring/drift_detector.py /monitoring/

# Copy static files (if needed for UI)
COPY api/static/ /api/static/

# Create directories for models and logs
RUN mkdir -p /models /logs/metrics /logs/predictions

# Set working directory
WORKDIR /api

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH=/models
ENV API_PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
