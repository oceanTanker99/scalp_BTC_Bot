# ====== Stage 1: Rust Builder ======
FROM rust:1.80-slim AS rust-builder
WORKDIR /build
COPY rust_engine/ ./rust_engine/
RUN cd rust_engine && cargo build --release

# ====== Stage 2: Python Runtime ======
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Buat user non-root untuk keamanan
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install procps untuk healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends procps && rm -rf /var/lib/apt/lists/*

# Copy compiled Rust library from builder stage
COPY --from=rust-builder /build/rust_engine/target/release/librust_engine.so /app/rust_engine/target/release/

# Copy Python source code
COPY main.py run_backtest.py run_parallel.py ./
COPY config/ ./config/
COPY src/ ./src/

# Ganti ke user non-root
RUN chown -R botuser:botuser /app
ENV NUMBA_CACHE_DIR=/tmp
USER botuser

# Healthcheck: pastikan proses Python masih jalan
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

# Run the bot
CMD ["python", "main.py"]
