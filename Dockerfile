FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py tracker.py menu.py ./

# Data dir — mount a PVC here in Kubernetes
RUN mkdir -p /data
ENV DATA_DIR=/data

EXPOSE 5050

CMD ["python3", "app.py"]
