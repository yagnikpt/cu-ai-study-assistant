# =============================================================================
# Stage 1: Build the frontend
# =============================================================================
# NOTE: Bun's react-dom/server shim doesn't export renderToPipeableStream,
# which React Router's build requires even in SPA mode. Use Node + Bun only
# as a package manager for speed, then build with Node.
FROM node:22-slim AS frontend-build
# FROM oven/bun:latest AS frontend-build

ENV VITE_API_BASE=""

RUN npm install -g bun
WORKDIR /app

# Copy workspace root files needed for dependency resolution
COPY package.json bun.lock ./
COPY frontend/package.json ./frontend/

# Install dependencies
RUN bun install --frozen-lockfile

# Copy frontend source and build
COPY frontend/ ./frontend/
RUN cd frontend && bunx react-router build

# =============================================================================
# Stage 2: Python backend + built frontend
# =============================================================================
FROM python:3.13-slim

WORKDIR /code

# Copy uv binary from its official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies for SSL connections to Neon PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Generate requirements.txt from pyproject.toml and install
COPY backend/pyproject.toml ./
RUN uv pip compile pyproject.toml -o requirements.txt && \
    pip install --no-cache-dir --upgrade -r requirements.txt

# Copy backend application code
COPY backend/app ./app

# Copy built frontend from stage 1
# React Router 7 (SPA mode) outputs to build/client/
COPY --from=frontend-build /app/frontend/build/client ./static

# Tell FastAPI where to find the frontend build
ENV STATIC_DIR=/code/static
ENV ENVIRONMENT=production

EXPOSE 8000

CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
