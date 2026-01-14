# Minimal Python image with Playwright for Cloud Run
FROM python:3.11-slim

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright && playwright install chromium --with-deps

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Copy Gujarat data
COPY ../gujarat-anyror-complete.json .

# Run as non-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Cloud Run uses PORT env var
ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
