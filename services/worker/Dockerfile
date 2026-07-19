# OCR worker (async, Redis queue). Build context = REPO ROOT.
#   docker build -f services/worker/Dockerfile -t ocr-worker .
FROM python:3.12-slim

WORKDIR /app

COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/__init__.py ./services/__init__.py
COPY services/common ./services/common
COPY services/worker ./services/worker

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.worker.ocr_worker"]
