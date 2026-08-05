FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir flask flask-cors python-dotenv pandas trino sqlalchemy apscheduler httpx requests

# Copy code
COPY "Manage care python" ./manage_care_python
COPY care_ai_engine ./care_ai_engine
COPY .env.template .

# Create Data directory for CSVs
RUN mkdir -p manage_care_python/Data

# Dashboard port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8001/ || exit 1

# Run dashboard server (serves CSVs and HTML)
CMD ["python", "-u", "manage_care_python/run_dashboard.py"]
