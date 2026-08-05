FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    flask \
    flask-cors \
    python-dotenv \
    pandas \
    trino \
    sqlalchemy \
    psycopg2-binary \
    httpx \
    requests

# Copy code
COPY "Manage care python" ./manage_care_python
COPY care_ai_engine ./care_ai_engine
COPY .env.template .

# Dashboard port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8001/api/status || exit 1

# Run Flask dashboard server (reads from PostgreSQL)
CMD ["python", "-u", "manage_care_python/dashboard_server.py"]
