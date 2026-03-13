FROM python:3.11-slim

WORKDIR /app

COPY deploy/finetune-metrics-exporter/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY deploy/finetune-metrics-exporter/exporter.py /app/exporter.py

EXPOSE 9101

CMD ["python", "exporter.py"]
