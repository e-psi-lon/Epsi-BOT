# syntax=docker/dockerfile:1

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

# Copy only necessary files for installation
COPY pyproject.toml README.md .env* ./
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
    libstdc++

# Copy only the installed packages
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
COPY epsi_bot ./epsi_bot
COPY .env* ./


# Create volume for data
VOLUME /app/data

# Command to start both memcached and your application
CMD ["python", "-m", "epsi_bot"]