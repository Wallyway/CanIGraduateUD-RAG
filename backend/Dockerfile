FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for build and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data directories exist
RUN mkdir -p /app/data/chroma /app/data/uploads /app/data/seed_documents

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

