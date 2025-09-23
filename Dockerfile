# Stage 1: Build Environment
FROM python:3.13-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    mariadb-dev \
    libffi-dev \
    python3-dev

# Copy necessary files for installation
COPY pyproject.toml README.md ./
COPY epsi_bot ./epsi_bot

# Install dependencies
RUN pip install --no-cache-dir --prefer-binary .

# Stage 2: Runtime Environment
FROM python:3.13-alpine AS final

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache \
    ffmpeg \
    memcached \
    mariadb-connector-c \
    libstdc++ \
    curl

# Create dedicated user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy only the installed packages
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin


RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# Copy essential environment files
# TODO: Move secrets to docker-compose
COPY --chown=appuser:appgroup .env* ./

ENV DOCKER_ENV=1

# Clean up unnecessary files to reduce image size
RUN find /usr/local -name "*.pyc" -delete && \
    find /usr/local -name "__pycache__" -delete && \
    rm -rf /usr/local/lib/python3.13/site-packages/pip* && \
    rm -rf /tmp/* /var/tmp/*

# Switch to non-root user
USER 1001:1001

# Create volume for data
VOLUME /app/data

# Health check 
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the application
# TODO: Change to ASGI server for production
CMD ["python", "-m", "epsi_bot"]