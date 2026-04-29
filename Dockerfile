FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py tracker.py menu.py ./
COPY app/ ./app/
COPY static/ ./static/

# Data dir — mount a PVC here in Kubernetes
RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 5050

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5050"]
