from __future__ import annotations

from threading import RLock

from app.schemas.output_report import AssessmentReport


class InMemoryAssessmentCache:
    """Thread-safe process-local cache; replace with Redis in a multi-replica deployment."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_key: dict[str, AssessmentReport] = {}
        self._job_to_key: dict[str, str] = {}

    def get(self, key: str) -> AssessmentReport | None:
        with self._lock:
            return self._by_key.get(key)

    def put(self, key: str, job_id: str, report: AssessmentReport) -> None:
        with self._lock:
            self._by_key[key] = report
            self._job_to_key[job_id] = key

    def get_job(self, job_id: str) -> AssessmentReport | None:
        with self._lock:
            key = self._job_to_key.get(job_id)
            return self._by_key.get(key) if key else None

