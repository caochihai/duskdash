# OCR Service (Máy 3)

OCR truyền thống qua **Azure AI Document Intelligence** (`prebuilt-read`) — trả text
**kèm toạ độ (bbox)** cho từng dòng/từ. Toạ độ này là nền cho:
- **Highlight kiểu NotebookLM** (click câu → tô đúng vùng trên tài liệu)
- **Bôi đen PII** theo vùng

Không chạy model local — mọi thứ qua API remote. `OCR_PROVIDER=mock` để chạy/test
không cần Azure (sinh bbox giả nhưng hợp lệ).

## Chạy local

```bash
pip install -r services/ocr/requirements.txt
# từ REPO ROOT (để import được libs/)
OCR_PROVIDER=mock uvicorn services.ocr.app:app --port 8300
```

## Env

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `OCR_PROVIDER` | `mock` | `azure` để dùng Azure thật |
| `AZURE_DI_ENDPOINT` | — | vd `https://<res>.cognitiveservices.azure.com` |
| `AZURE_DI_KEY` | — | key tài nguyên Document Intelligence |
| `AZURE_DI_MODEL` | `prebuilt-read` | model OCR |
| `AZURE_DI_API_VERSION` | `2024-11-30` | api version |

## API

- `GET  /health`
- `POST /ocr/extract` — `{document_id, mime_type, file_b64|file_url}` → `DocumentOCR`
- `POST /ocr/redact`  — `{document_id, mime_type, file_b64, boxes:[BBox]}` → `{redacted_b64}`

Schema: `libs/contracts/ocr.py`, `libs/contracts/geometry.py`.

## Docker

```bash
# build context PHẢI là repo root
docker build -f services/ocr/Dockerfile -t ocr-service .
docker run -p 8300:8300 -e OCR_PROVIDER=mock ocr-service
```
