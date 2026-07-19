from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.orchestration.pipeline import AssessmentExecution, AssessmentPipeline
from app.schemas.input_extracted_bundle import ExtractedCaseBundle
from app.schemas.output_report import AssessmentReport


router = APIRouter(prefix="/v1/assess", tags=["assessment"])


def get_pipeline(request: Request) -> AssessmentPipeline:
    return request.app.state.pipeline


@router.post("", response_model=AssessmentExecution)
def create_assessment(
    bundle: ExtractedCaseBundle,
    pipeline: AssessmentPipeline = Depends(get_pipeline),
) -> AssessmentExecution:
    return pipeline.assess(bundle)


@router.get("/{job_id}", response_model=AssessmentReport)
def get_assessment(
    job_id: str,
    pipeline: AssessmentPipeline = Depends(get_pipeline),
) -> AssessmentReport:
    report = pipeline.get_job(job_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment job not found")
    return report
