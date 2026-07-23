FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Buat user non-root untuk keamanan
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install procps (healthcheck), curl, and build-essential for Rust compilation
RUN apt-get update && apt-get install -y procps curl build-essential && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

COPY . .

# Compile Rust engine into a shared library (.so for Linux)
RUN cd rust_engine && cargo build --release

# Ganti ke user non-root
RUN chown -R botuser:botuser /app
ENV NUMBA_CACHE_DIR=/tmp
USER botuser

# Healthcheck: pastikan proses Python masih jalan
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

# Run the bot
CMD ["python", "main.py"]
