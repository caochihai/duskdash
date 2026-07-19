# Deep-Research Engine (Máy 2). Build context = REPO ROOT (cần cả libs/ lẫn services/).
#   docker build -f services/engine/Dockerfile -t engine-service .
FROM python:3.12-slim

WORKDIR /app

COPY services/engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY libs ./libs
COPY services/__init__.py ./services/__init__.py
COPY services/engine ./services/engine

ENV PYTHONPATH=/app
ENV LLM_PROVIDER=mock
ENV DATA_PROVIDER=mock
EXPOSE 8200

CMD ["uvicorn", "services.engine.app:app", "--host", "0.0.0.0", "--port", "8200"]
