FROM python:3.13-slim

# Non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Install deps as root before dropping privileges
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt 2>/dev/null || \
    pip install --no-cache-dir -r requirements.txt

COPY main.py ./
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Data dir — mount a PVC here in Kubernetes
RUN mkdir -p /data && chown appuser:appgroup /data

ENV DATA_DIR=/data

# Drop to non-root
USER appuser

EXPOSE 5050

# Explicit host binding — never 0.0.0.0 in prod without a reverse proxy
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5050", "--no-access-log"]
