FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by chromadb and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces requires port 7860
EXPOSE 7860

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860"]
