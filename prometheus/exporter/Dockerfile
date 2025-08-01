FROM python:3.11-slim

WORKDIR /app

COPY metrics_exporter.py .

COPY prometheus-requirements.txt .

RUN pip install -r prometheus-requirements.txt

CMD ["uvicorn", "metrics_exporter:app", "--host", "0.0.0.0", "--port", "9123"]