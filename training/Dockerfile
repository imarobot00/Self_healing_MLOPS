# ================================
# Stage 1: Builder
# ================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY training/requirements.txt .

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
RUN mkdir -p /training /api /monitoring

# Copy application files (preserve structure)
COPY training/training.py /training/
COPY training/auto_trainer.py /training/
COPY training/model_validator.py /training/
COPY training/model_registry.py /training/
COPY training/self_healing_orchestrator.py /training/
COPY training/metrics_collector.py /training/
COPY training/alert_manager.py /training/
COPY training/health_checks.py /training/
COPY training/health_server.py /training/
COPY training/run_training_service.py /training/
COPY training/run_orchestrator_service.py /training/

# Copy shared dependencies from API
COPY api/feature_engineer.py /api/
COPY api/schemas.py /api/

# Copy monitoring dependencies
COPY monitoring/drift_detector.py /monitoring/

# Set working directory
WORKDIR /training

# Create necessary directories
RUN mkdir -p \
    /models \
    /logs \
    /charts \
    /evaluations \
    /validations \
    /orchestrator_logs \
    /data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH=/models
ENV DATA_PATH=/data
ENV TRAINING_PORT=8001
ENV TRAINING_CHECK_INTERVAL=300
ENV ORCHESTRATOR_CHECK_INTERVAL=180
ENV ORCHESTRATOR_PORT=8002

# Expose ports for metrics (training + orchestrator)
EXPOSE 8001 8002

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command - run the long-running training service
CMD ["python", "run_training_service.py"]
