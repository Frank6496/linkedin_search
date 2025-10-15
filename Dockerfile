
# Use a slim Python image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (optional)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install a production server (optional; uvicorn is fine alone)
RUN pip install --no-cache-dir gunicorn

COPY . .

# Expose port
ENV PORT=8000
EXPOSE 8000

# Start
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
