FROM python:3.11-slim

# Create non-root user for OpenShift compatibility
RUN useradd -m -u 1001 appuser && \
    mkdir -p /app && \
    chown -R 1001:0 /app && \
    chmod -R g+rwX /app

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Set ownership for OpenShift
RUN chown -R 1001:0 /app && \
    chmod -R g+rwX /app

# Switch to non-root user
USER 1001

# Expose port
EXPOSE 8004

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8004/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]