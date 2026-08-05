FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY care_ai_engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy skill code
COPY care_ai_engine ./care_ai_engine
COPY .env.template .

# Run the skill scheduler + FastAPI server
CMD ["python", "-m", "care_ai_engine.main"]
