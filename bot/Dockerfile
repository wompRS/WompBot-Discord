FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
# SECURITY: upgrade build toolchain first (clears pip/wheel/setuptools CVEs)
# PERF: install CPU-only torch first (from the PyTorch CPU index) so llmlingua does
#       not pull the multi-GB CUDA build + ~15 nvidia-* wheels into this CPU-only image.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir --timeout=180 --retries=5 torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

# SECURITY: Create non-root user to run the application
RUN useradd -m -u 1000 -s /bin/bash botuser && \
    chown -R botuser:botuser /app

# Copy application code with correct ownership
COPY --chown=botuser:botuser . .

# SECURITY: Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "-u", "main.py"]
