# Multi-stage Dockerfile for Solana Moon Scanner

# Stage 1: Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 scanner && \
    chown -R scanner:scanner /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/scanner/.local

# Copy application code
COPY --chown=scanner:scanner . .

# Create necessary directories
RUN mkdir -p logs data && \
    chown -R scanner:scanner logs data

# Switch to non-root user
USER scanner

# Add local bin to PATH
ENV PATH=/home/scanner/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Expose Prometheus metrics port
EXPOSE 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "-m", "src.cli", "monitor"]
