"""Azure AI Document Intelligence — model 'prebuilt-read' (OCR truyền thống).

Trả text KÈM polygon toạ độ cho từng dòng/từ → dựng bbox chuẩn hoá để highlight
và bôi đen. Gọi REST trực tiếp qua httpx (không cần Azure SDK), theo luồng:
POST :analyze -> nhận Operation-Location -> poll GET tới khi 'succeeded'.
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

import httpx

from libs.contracts.geometry import BBox
from libs.contracts.ocr import DocumentOCR, OcrLine, OcrPage, OcrWord


class AzureReadProvider:
    provider = "azure-read"

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        model: str = "prebuilt-read",
        api_version: str = "2024-11-30",
        poll_interval: float = 1.5,
        poll_timeout: float = 120.0,
        http_timeout: float = 60.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._key = key
        self.model = model
        self._api_version = api_version
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout
        self._http_timeout = http_timeout

    async def extract(
        self, content: bytes, *, mime_type: str, document_id: UUID
    ) -> DocumentOCR:
        analyze_url = (
            f"{self._endpoint}/documentintelligence/documentModels/"
            f"{self.model}:analyze?api-version={self._api_version}"
        )
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            resp = await self._request_with_retry(
                client, "POST", analyze_url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._key,
                    "Content-Type": "application/octet-stream",
                },
                content=content,
            )
            op_location = resp.headers.get("Operation-Location")
            if not op_location:
                raise RuntimeError("Azure không trả Operation-Location")

            data = await self._poll(client, op_location)

        return self._parse(data.get("analyzeResult", {}), document_id)

    async def _request_with_retry(
        self, client: httpx.AsyncClient, method: str, url: str,
        *, max_retries: int = 6, **kwargs,
    ) -> httpx.Response:
        """Gọi HTTP với retry khi 429/503 (backoff mũ, tôn trọng Retry-After)."""
        delay = 1.0
        for attempt in range(max_retries + 1):
            r = await client.request(method, url, **kwargs)
            if r.status_code not in (429, 503) or attempt == max_retries:
                r.raise_for_status()
                return r
            retry_after = r.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            await asyncio.sleep(wait)
            delay = min(delay * 2, 20.0)
        raise RuntimeError("unreachable")

    async def _poll(self, client: httpx.AsyncClient, op_location: str) -> dict:
        started = time.monotonic()
        while True:
            r = await self._request_with_retry(
                client, "GET", op_location,
                headers={"Ocp-Apim-Subscription-Key": self._key},
            )
            data = r.json()
            status = data.get("status")
            if status == "succeeded":
                return data
            if status == "failed":
                raise RuntimeError(f"Azure OCR failed: {data.get('error')}")
            if time.monotonic() - started > self._poll_timeout:
                raise TimeoutError("Azure OCR quá thời gian chờ")
            await asyncio.sleep(self._poll_interval)

    def _parse(self, analyze_result: dict, document_id: UUID) -> DocumentOCR:
        full_text = analyze_result.get("content", "")
        pages_out: list[OcrPage] = []
        for page in analyze_result.get("pages", []):
            pnum = int(page.get("pageNumber", 1))
            pw = float(page.get("width") or 1.0)
            ph = float(page.get("height") or 1.0)
            unit = page.get("unit", "pixel")
            words = page.get("words", [])

            lines_out: list[OcrLine] = []
            for line in page.get("lines", []):
                spans = line.get("spans") or [{}]
                first = spans[0]
                loff = int(first.get("offset", -1))
                llen = int(first.get("length", 0))
                members = self._words_in_span(words, pnum, pw, ph, loff, llen)
                conf = (
                    sum(w.confidence for w in members) / len(members)
                    if members
                    else 0.0
                )
                try:
                    bbox = BBox.from_polygon(
                        page=pnum, polygon=line["polygon"],
                        page_width=pw, page_height=ph,
                    )
                except Exception:  # noqa: BLE001 - dòng thiếu polygon thì bỏ qua
                    continue
                lines_out.append(
                    OcrLine(text=line.get("content", ""), bbox=bbox,
                            confidence=conf, words=tuple(members))
                )
            pages_out.append(
                OcrPage(page=pnum, width=pw, height=ph, unit=unit,
                        lines=tuple(lines_out))
            )
        return DocumentOCR(
            document_id=document_id, provider=self.provider, model=self.model,
            full_text=full_text, pages=tuple(pages_out),
        )

    @staticmethod
    def _words_in_span(
        words: list, page: int, pw: float, ph: float, loff: int, llen: int
    ) -> list[OcrWord]:
        out: list[OcrWord] = []
        for w in words:
            span = w.get("span", {})
            woff = int(span.get("offset", -2))
            if not (loff <= woff < loff + llen):
                continue
            try:
                bbox = BBox.from_polygon(
                    page=page, polygon=w["polygon"], page_width=pw, page_height=ph
                )
            except Exception:  # noqa: BLE001
                continue
            out.append(
                OcrWord(text=w.get("content", ""), bbox=bbox,
                        confidence=float(w.get("confidence", 0.0)))
            )
        return out
