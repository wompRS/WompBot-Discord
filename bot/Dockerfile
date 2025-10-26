FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# SECURITY: Create non-root user to run the application
RUN useradd -m -u 1000 -s /bin/bash botuser && \
    chown -R botuser:botuser /app

# Copy application code with correct ownership
COPY --chown=botuser:botuser . .

# SECURITY: Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "-u", "main.py"]
