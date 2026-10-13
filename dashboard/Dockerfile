# Stage 1: build the React console.
FROM --platform=$BUILDPLATFORM node:22-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime. Code Engine sends traffic to PORT (8080 by default).
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PORT=8080 DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app /app/app
COPY --from=frontend /build/frontend/dist /app/frontend/dist
RUN mkdir -p /app/data && chown -R root:0 /app && chmod -R g+rwX /app
EXPOSE 8080
USER 1001
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
