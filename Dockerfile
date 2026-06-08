FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Buat user non-root untuk keamanan
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install procps untuk pgrep di Healthcheck
RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

COPY . .

# Ganti ke user non-root
RUN chown -R botuser:botuser /app
ENV NUMBA_CACHE_DIR=/tmp
USER botuser

# Healthcheck: pastikan proses Python masih jalan
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

# Run the bot
CMD ["python", "main.py"]
