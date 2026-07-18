# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install .

FROM builder AS test
COPY tests ./tests
RUN python -m pip install '.[dev]'
CMD ["python", "-m", "pytest", "tests/unit", "tests/contract"]

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

RUN groupadd --gid 10001 bankapp \
    && useradd --uid 10001 --gid bankapp --create-home --shell /usr/sbin/nologin bankapp

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=bankapp:bankapp app ./app

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
