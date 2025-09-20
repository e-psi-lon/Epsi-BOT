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
    libstdc++


# Copy only the installed packages
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy essential environment files
TODO: Move to docker-compose 
COPY .env* ./

ENV DOCKER_ENV=1

# Clean up unnecessary files to reduce image size
RUN find /usr/local -name "*.pyc" -delete && \
    find /usr/local -name "__pycache__" -delete && \
    rm -rf /usr/local/lib/python3.13/site-packages/pip* && \
    rm -rf /tmp/* /var/tmp/*

# Create volume for data
VOLUME /app/data

# Start the application
# TODO: Change to ASGI server for production
CMD ["python", "-m", "epsi_bot"]