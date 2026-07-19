# OCR service (Máy 3). Build context = REPO ROOT (cần cả libs/ lẫn services/ocr/).
#   docker build -f services/ocr/Dockerfile -t ocr-service .
FROM python:3.12-slim

WORKDIR /app

# PyMuPDF & Pillow chạy wheel sẵn; không cần build tool nặng
COPY services/ocr/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY libs ./libs
COPY services/__init__.py ./services/__init__.py
COPY services/ocr ./services/ocr

ENV PYTHONPATH=/app
ENV OCR_PROVIDER=mock
EXPOSE 8300

CMD ["uvicorn", "services.ocr.app:app", "--host", "0.0.0.0", "--port", "8300"]
